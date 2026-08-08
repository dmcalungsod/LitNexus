import logging
import requests
import queue
import threading
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)

class ReferenceEngine(threading.Thread):
    def __init__(
        self,
        dois: list[str],
        db_manager: Any,
        progress_queue: queue.Queue,
        email: str = None
    ):
        super().__init__(daemon=True)
        self.dois = dois
        self.db = db_manager
        self.queue = progress_queue
        self.email = email or "test@example.com"
        
        self._cancel_event = threading.Event()
        self.executor = None

    def log(self, message: str, color: str = None):
        self.queue.put({
            "status": "reference_log",
            "message": message,
            "color": color
        })

    def run(self):
        op_id = start_operation()
        logger.info(f"Starting reference fetch for DOIs: {self.dois}", extra={"event": "reference_start"})
        
        if not self.dois:
            self.queue.put({"status": "reference_finished"})
            return
            
        self.log(f"Starting Reference Fetcher for {len(self.dois)} papers...", "light_blue")
        
        self.executor = ThreadPoolExecutor(max_workers=3)
        futures = []
        for doi in self.dois:
            if self._cancel_event.is_set():
                break
            f = self.executor.submit(self._fetch_references, doi)
            futures.append(f)
            
        for future in futures:
            if self._cancel_event.is_set():
                break
            try:
                future.result()
            except Exception as e:
                self.log(f"Error fetching references: {e}", "red")
                
        self.executor.shutdown(wait=False)
        if self._cancel_event.is_set():
            self.log("Reference Fetching cancelled.", "orange")
        else:
            self.log("Reference Fetching complete.", "green")
            
        self.queue.put({"status": "reference_finished"})

    def cancel(self):
        self._cancel_event.set()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _fetch_references(self, seed_doi: str):
        if self._cancel_event.is_set():
            return
            
        headers = {"User-Agent": f"PDFRetriever-RefEngine/1.0 (mailto:{self.email})"}
        
        self.log(f"Resolving {seed_doi} to get referenced works...")
        url = f"https://api.openalex.org/works/https://doi.org/{seed_doi}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 404:
                self.log(f"{seed_doi} not found in OpenAlex.", "orange")
                return
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            self.log(f"Network error resolving {seed_doi}: {e}", "red")
            return
            
        referenced_works = data.get("referenced_works", [])
        expected_count = data.get("referenced_works_count", len(referenced_works))
        
        if not referenced_works:
            self.log(f"No references found for {seed_doi} in OpenAlex.", "orange")
            if expected_count == 0:
                self.db.update_fetch_status(seed_doi, "references", "complete")
            return
            
        expected_count = data.get("referenced_works_count", len(referenced_works))
        
        self.log(f"Found {len(referenced_works)} references for {seed_doi}. Fetching metadata...", "light_blue")
        
        # We process in batches of 50
        batch_size = 50
        ids = [w.split("/")[-1] for w in referenced_works]
        
        parent_gen = self.db.get_paper_generation(seed_doi)
        child_gen = parent_gen - 1 # Backward snowballing goes negative
        
        added_count = 0
        
        for i in range(0, len(ids), batch_size):
            if self._cancel_event.is_set():
                break
                
            batch_ids = ids[i:i+batch_size]
            filter_str = "openalex:" + "|".join(batch_ids)
            batch_url = f"https://api.openalex.org/works?filter={filter_str}&per-page={batch_size}&select=doi,title,publication_year,authorships,abstract_inverted_index"
            
            try:
                batch_resp = requests.get(batch_url, headers=headers, timeout=15)
                batch_resp.raise_for_status()
                batch_data = batch_resp.json()
            except requests.RequestException as e:
                self.log(f"Error fetching reference metadata batch: {e}", "red")
                continue
                
            results = batch_data.get("results", [])
            for item in results:
                child_doi_url = item.get("doi")
                if not child_doi_url:
                    continue
                    
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
                
                try:
                    # Insert the referenced paper (if exists, ignore)
                    self.db.add_paper(child_doi, title=title, authors=authors, year=year, abstract=abstract, generation=child_gen)
                    self.db.add_edge(seed_doi, child_doi)
                    # Record discovery
                    self.db.add_discovery(child_doi, seed_doi, "reference", child_gen)
                    added_count += 1
                except Exception as e:
                    logger.error(f"DB Error saving reference DOI {child_doi}: {e}", extra={"event": "db_error", "doi": child_doi})
                    
        status = "complete" if added_count >= expected_count else "partial"
        self.db.update_fetch_status(seed_doi, "references", status)
        
        if added_count < expected_count:
            self.log(f"Retrieved {added_count}/{expected_count} known references for {seed_doi} ({expected_count - added_count} could not be resolved).", "orange")
        else:
            self.log(f"Retrieved all {added_count} known references for {seed_doi}.", "green")
