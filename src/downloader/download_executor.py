from src.downloader.logging_config import get_logger, start_operation
import threading
from typing import Any

from .source_manager import SourceManager
from .types import DownloadContext

logger = get_logger(__name__)

class DownloadExecutor:
    def __init__(self, source_manager: SourceManager, stats: dict[str, Any], stats_lock: threading.Lock):
        self.source_manager = source_manager
        self.stats = stats
        self._stats_lock = stats_lock

    def _record_outcome(self, doi: str, source_name: str, filename: str):
        with self._stats_lock:
            self.stats["success"] += 1
            self.stats["sources"][source_name] = (
                self.stats["sources"].get(source_name, 0) + 1
            )
        logger.info(f"Success ({source_name}): {doi} -> {filename}")

    def check_if_skipped(self, ctx: DownloadContext) -> dict[str, Any] | None:
        if ctx.filepath.exists() and ctx.filepath.stat().st_size > 5000:
            with self._stats_lock:
                self.stats["skipped"] += 1
            return {
                "doi": ctx.doi,
                "status": "skipped",
                "filename": str(ctx.filepath),
                "citation": ctx.citation,
            }
        return None

    def try_primary_pdf(self, primary_pdf_url: str | None, ctx: DownloadContext) -> dict[str, Any] | None:
        if not primary_pdf_url:
            return None
        if ctx.cancel_event and ctx.cancel_event.is_set():
            return None
            
        if self.source_manager.unpaywall_source._fetch_and_save(primary_pdf_url, ctx.filepath):
            self._record_outcome(ctx.doi, "Unpaywall", ctx.filename)
            return {
                "doi": ctx.doi,
                "status": "success",
                "source": "Unpaywall",
                "filename": str(ctx.filepath),
                "citation": ctx.citation,
            }
        return None

    def try_pipeline_sources(self, ctx: DownloadContext) -> dict[str, Any] | None:
        for source in self.source_manager.pipeline:
            if ctx.cancel_event and ctx.cancel_event.is_set():
                return {
                    "doi": ctx.doi,
                    "status": "error",
                    "message": "Cancelled mid-pipeline",
                }
            try:
                if source.download(ctx.doi, ctx.filepath, ctx.metadata):
                    self._record_outcome(ctx.doi, source.name, ctx.filename)
                    return {
                        "doi": ctx.doi,
                        "status": "success",
                        "source": source.name,
                        "filename": str(ctx.filepath),
                        "citation": ctx.citation,
                    }
            except Exception as e:
                logger.warning(f"{source.name} failed: {e}")
        return None
