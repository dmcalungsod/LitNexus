import logging
import requests
import queue
from typing import Any
from concurrent.futures import ThreadPoolExecutor
import threading
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)

class MetadataResolverEngine(threading.Thread):
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
            "status": "resolver_log",
            "message": message,
            "color": color
        })

    def run(self):
        op_id = start_operation()
        logger.info(f"Starting metadata resolution for DOIs: {self.dois}", extra={"event": "metadata_resolve_start"})
        
        if not self.dois:
            self.queue.put({"status": "resolver_finished"})
            return
            
        self.log(f"Starting Metadata Resolver for {len(self.dois)} DOIs...", "light_blue")
        
        self.executor = ThreadPoolExecutor(max_workers=5)
        futures = []
        for doi in self.dois:
            if self._cancel_event.is_set():
                break
            f = self.executor.submit(self._resolve_single_doi, doi)
            futures.append(f)
            
        for future in futures:
            if self._cancel_event.is_set():
                break
            try:
                future.result()
            except Exception as e:
                self.log(f"Error resolving: {e}", "red")
                
        self.executor.shutdown(wait=False)
        if self._cancel_event.is_set():
            self.log("Metadata Resolution cancelled.", "orange")
        else:
            self.log("Metadata Resolution complete.", "green")
            
        self.queue.put({"status": "resolver_finished"})

    def cancel(self):
        self._cancel_event.set()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def _resolve_single_doi(self, doi: str):
        if self._cancel_event.is_set():
            return
            
        headers = {"User-Agent": f"PDFRetriever-Resolver/1.0 (mailto:{self.email})"}
        
        lookup_url = f"https://api.openalex.org/works/https://doi.org/{doi}?select=doi,title,publication_year,authorships,abstract_inverted_index,referenced_works_count,cited_by_count"
        
        try:
            resp = requests.get(lookup_url, headers=headers, timeout=10)
            if resp.status_code == 404:
                return
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return
            
        title = data.get("title")
        year = data.get("publication_year")
        ext_ref = data.get("referenced_works_count")
        ext_cite = data.get("cited_by_count")
        
        # Parse Authors
        authors = None
        authorships = data.get("authorships", [])
        if authorships:
            author_names = [a.get("author", {}).get("display_name", "") for a in authorships]
            authors = ", ".join([n for n in author_names if n])
            
        # Parse Abstract
        abstract = None
        inverted_index = data.get("abstract_inverted_index")
        if inverted_index:
            words_dict = {}
            for word, positions in inverted_index.items():
                for pos in positions:
                    words_dict[pos] = word
            abstract = " ".join([words_dict[pos] for pos in sorted(words_dict.keys())])
        
        if title:
            try:
                self.db.update_paper_metadata(doi, title=title, year=year, authors=authors, abstract=abstract, ext_ref=ext_ref, ext_cite=ext_cite)
                # Tell the UI a row updated, we'll just queue a refresh trigger
                self.queue.put({"status": "resolver_item_done", "doi": doi})
            except Exception as e:
                logger.error(f"DB Error updating metadata for DOI {doi}: {e}", extra={"event": "db_error", "doi": doi})
