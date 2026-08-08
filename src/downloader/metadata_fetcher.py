from src.downloader.logging_config import get_logger, start_operation
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .source_manager import SourceManager
from .sources import Source

logger = get_logger(__name__)

class MetadataFetcher:
    def __init__(self, source_manager: SourceManager):
        self.source_manager = source_manager

    def _fetch_single_source_metadata(self, source: Source, doi: str) -> tuple[dict[str, Any] | None, str | None, str]:
        try:
            temp_meta = source.get_metadata(doi)
            pdf_url = temp_meta.get("_pdf_url") if temp_meta else None
            return temp_meta, pdf_url, source.name
        except Exception:
            return None, None, source.name

    def _process_metadata_result(self, future: Any, current_metadata: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None, bool]:
        """
        Processes a single future result from metadata fetching.
        Returns (updated_metadata, primary_pdf_url, should_break).
        """
        try:
            temp_meta, pdf_url, source_name = future.result()
            high_confidence_sources = {"Crossref", "Unpaywall"}
            
            if temp_meta and not current_metadata:
                current_metadata = temp_meta
                # Short-circuit: stop if we got high-confidence source
                if source_name in high_confidence_sources and current_metadata.get("title"):
                    return current_metadata, pdf_url, True
                return current_metadata, pdf_url, False
        except Exception:
            pass
        return current_metadata, None, False

    def fetch_metadata(self, doi: str) -> tuple[dict[str, Any] | None, str | None]:
        """
        Fetches metadata from multiple sources in parallel and returns the best result.
        Stops early if a high-confidence source (Crossref, Unpaywall) succeeds.
        """
        metadata = None
        primary_pdf_url = None
        
        # Parallel fetch with max 4 workers to respect API rate limits
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self._fetch_single_source_metadata, s, doi): s for s in self.source_manager.metadata_sources}
            
            for future in as_completed(futures):
                metadata, pdf_url, should_break = self._process_metadata_result(future, metadata)
                if pdf_url:
                    primary_pdf_url = pdf_url
                if should_break:
                    break
        
        return metadata, primary_pdf_url
