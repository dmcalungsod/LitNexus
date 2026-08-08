import logging
import requests
import queue
import threading
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor, Future
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)

class SnowballEngine(threading.Thread):
    def __init__(
        self,
        dois: list[str],
        db_manager: Any,
        progress_queue: queue.Queue,
        openalex_api_key: str = None,
        email: str = None
    ):
        super().__init__(daemon=True)
        self.dois = dois
        self.db = db_manager
        self.queue = progress_queue
        self.openalex_api_key = openalex_api_key
        self.email = email or "test@example.com"
        
        self._cancel_event = threading.Event()
        self.executor = None

    def log(self, message: str, color: str = None):
        self.queue.put({
            "status": "snowball_log",
            "message": message,
            "color": color
        })

    def run(self):
        op_id = start_operation()
        logger.info(f"Starting snowball run for DOIs: {self.dois}", extra={"event": "snowball_start"})
        
        if not self.dois:
            self.queue.put({"status": "snowball_finished"})
            return
            
        self.log(f"Starting Snowball Engine for {len(self.dois)} papers...", "light_blue")
        
        self.executor = ThreadPoolExecutor(max_workers=5)
        futures = []
        for doi in self.dois:
            if self._cancel_event.is_set():
                break
            f = self.executor.submit(self._snowball_single_doi, doi)
            futures.append(f)
            
        for future in futures:
            if self._cancel_event.is_set():
                break
            try:
                future.result()
            except Exception as e:
                self.log(f"Error snowballing: {e}", "red")
                
        self.executor.shutdown(wait=False)
        if self._cancel_event.is_set():
            self.log("Snowballing cancelled.", "orange")
        else:
            self.log("Snowballing complete.", "green")
            
        self.queue.put({"status": "snowball_finished"})

    def cancel(self):
        self._cancel_event.set()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _snowball_single_doi(self, doi: str):
        if self._cancel_event.is_set():
            return
            
        headers = {"User-Agent": f"PDFRetriever-Snowball/1.0 (mailto:{self.email})"}
        
        # Step 1: Look up OpenAlex ID for the DOI
        self.log(f"Resolving {doi} in OpenAlex...", "white")
        lookup_url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        
        try:
            resp = requests.get(lookup_url, headers=headers, timeout=10)
            if resp.status_code == 404:
                self.log(f"OpenAlex has no record for {doi}.", "orange")
                return
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            self.log(f"Failed to lookup {doi}: {e}", "red")
            return
            
        openalex_id = data.get("id")
        if not openalex_id:
            self.log(f"Could not find OpenAlex ID for {doi}.", "orange")
            return
            
        # Extract the short ID (W3177828909) from https://openalex.org/W3177828909
        short_id = openalex_id.split("/")[-1]
        
        # Step 2: Fetch citing papers
        self.log(f"Fetching citing papers for {doi} ({short_id})...", "white")
        cites_url = f"https://api.openalex.org/works?filter=cites:{short_id}&select=doi,title,publication_year,authorships,abstract_inverted_index&per-page=50"
        
        try:
            cites_resp = requests.get(cites_url, headers=headers, timeout=10)
            cites_resp.raise_for_status()
            cites_data = cites_resp.json()
        except requests.RequestException as e:
            self.log(f"Failed to fetch citing works for {doi}: {e}", "red")
            return
            
        results = cites_data.get("results", [])
        expected_count = cites_data.get("meta", {}).get("count", len(results))
        if not results:
            self.log(f"No citing papers found for {doi}.", "orange")
            if expected_count == 0:
                self.db.update_fetch_status(doi, "citations", "complete")
            return
            
        self.log(f"Found {len(results)} citing papers for {doi}. Saving to database...", "green")
        
        added_count = 0
        parent_gen = self.db.get_paper_generation(doi)
        child_gen = parent_gen + 1
        
        for item in results:
            child_doi_url = item.get("doi")
            if not child_doi_url:
                continue
                
            # Clean doi (e.g. https://doi.org/10.1038/xyz -> 10.1038/xyz)
            child_doi = child_doi_url.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
            title = item.get("title")
            year = item.get("publication_year")
            
            # Parse Authors
            authors = None
            authorships = item.get("authorships", [])
            if authorships:
                author_names = [a.get("author", {}).get("display_name", "") for a in authorships]
                authors = ", ".join([n for n in author_names if n])
                
            # Parse Abstract
            abstract = None
            inverted_index = item.get("abstract_inverted_index")
            if inverted_index:
                words_dict = {}
                for word, positions in inverted_index.items():
                    for pos in positions:
                        words_dict[pos] = word
                abstract = " ".join([words_dict[pos] for pos in sorted(words_dict.keys())])
            
            # Record it in the DB
            try:
                # Add child paper if not exists (will ignore if duplicate)
                self.db.add_paper(child_doi, title=title, authors=authors, year=year, abstract=abstract, generation=child_gen)
                # Link them. The child cites the parent. So (source=child, target=doi)
                self.db.add_edge(child_doi, doi)
                # Record discovery
                self.db.add_discovery(child_doi, doi, "citation", child_gen)
                added_count += 1
            except Exception as e:
                logger.error(f"DB Error saving citing DOI {child_doi}: {e}", extra={"event": "db_error", "doi": child_doi})
                
        status = "complete" if added_count >= expected_count else "partial"
        self.db.update_fetch_status(doi, "citations", status)
        
        if added_count < expected_count:
            self.log(f"Retrieved {added_count}/{expected_count} known future citations for {doi} ({expected_count - added_count} could not be resolved).", "orange")
        else:
            self.log(f"Retrieved all {added_count} known future citations for {doi}.", "green")
