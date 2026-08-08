from src.downloader.logging_config import get_logger, start_operation
import threading
from pathlib import Path
from typing import Any

from .download_executor import DownloadExecutor
from .filename_generator import FilenameGenerator
from .metadata_fetcher import MetadataFetcher
from .source_manager import SourceManager
from .types import DownloadContext
from .utils import format_authors_apa

logger = get_logger(__name__)

class DownloadPipeline:
    def __init__(self, source_manager: SourceManager, output_dir: Path, stats: dict[str, Any], stats_lock: threading.Lock):
        self.source_manager = source_manager
        self.output_dir = output_dir
        self.stats = stats
        self._stats_lock = stats_lock
        self.metadata_fetcher = MetadataFetcher(self.source_manager)
        self.filename_generator = FilenameGenerator()
        self.download_executor = DownloadExecutor(self.source_manager, self.stats, self._stats_lock)

    def _create_download_context(self, doi: str, cancel_event: threading.Event | None) -> tuple[DownloadContext | None, str | None, dict[str, Any] | None]:
        """
        Orchestrates metadata fetching and context creation.
        Returns (DownloadContext, primary_pdf_url, error_dict).
        """
        if cancel_event and cancel_event.is_set():
            return None, None, {"doi": doi, "status": "error", "message": "Cancelled before start"}

        # Fetch metadata using MetadataFetcher
        metadata, primary_pdf_url = self.metadata_fetcher.fetch_metadata(doi)

        if cancel_event and cancel_event.is_set():
             return None, None, {"doi": doi, "status": "error", "message": "Cancelled during metadata fetch"}

        if metadata is None:
            metadata = {"doi": doi}

        filename = self.filename_generator.generate_filename(metadata)
        filepath = self.output_dir / filename

        authors = metadata.get("authors", [])
        year = metadata.get("year", "n.d.")
        author_str = format_authors_apa(authors)
        citation = f"{author_str}, {year}" if author_str else year

        ctx = DownloadContext(
            doi=doi,
            filepath=filepath,
            filename=filename,
            citation=citation,
            metadata=metadata,
            cancel_event=cancel_event
        )
        return ctx, primary_pdf_url, None

    def download_one(self, doi: str, cancel_event: threading.Event | None = None) -> dict[str, Any]:
        """Runs full download pipeline for one DOI with cancel support."""
        ctx, primary_pdf_url, error = self._create_download_context(doi, cancel_event)
        if error:
            return error
        if not ctx: # Should be covered by error check, but for safety
            return {"doi": doi, "status": "failed", "message": "Context creation failed"}

        if skipped_result := self.download_executor.check_if_skipped(ctx):
            return skipped_result

        # Try primary PDF URL from high-confidence source (usually Unpaywall)
        if primary_result := self.download_executor.try_primary_pdf(primary_pdf_url, ctx):
            return primary_result

        # Try remaining pipeline sources
        if pipeline_result := self.download_executor.try_pipeline_sources(ctx):
            return pipeline_result

        if cancel_event and cancel_event.is_set():
            return {"doi": doi, "status": "error", "message": "Cancelled before finish"}

        with self._stats_lock:
            self.stats["fail"] += 1
        return {"doi": doi, "status": "failed", "message": "No valid source found"}
