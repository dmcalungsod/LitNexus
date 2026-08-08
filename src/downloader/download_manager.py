"""
DownloadManager (Controller/Model)

Handles concurrent downloads, queue updates, and safe cancellation.
Decoupled from the GUI layer.
"""

import queue
import threading
from concurrent.futures import (
    CancelledError,
    Future,
    ThreadPoolExecutor,
    TimeoutError,
    as_completed,
)
from pathlib import Path
from typing import Any

from .core import Downloader
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)


class DownloadManager(threading.Thread):
    """Manages the concurrent download process."""

    def __init__(
        self,
        settings: dict,
        progress_queue: queue.Queue,
        dois: list[str],
        failed_dois_path: Path,
    ):
        super().__init__(daemon=True)

        self.settings = settings
        self.progress_queue = progress_queue
        self.dois = dois

        self.failed_dois_path = failed_dois_path
        self.fail_lock = threading.Lock()

        self.downloader = Downloader(
            output_dir=settings.get("output_dir", str(Path.home() / "Downloads" / "LitNexus")),
            email=settings.get("email", ""),
            core_api_key=settings.get("core_api_key"),
            verify_ssl=settings.get("verify_ssl", True),
            openalex_api_key=settings.get("openalex_api_key"),
        )
        self.executor = None
        self.future_map: dict[Future[Any], str] = {}
        self._cancel_event = threading.Event()

    def _log_failure(self, doi: str):
        """Thread-safely appends a failed DOI to the designated file."""
        try:
            with self.fail_lock:
                with open(self.failed_dois_path, "a", encoding="utf-8") as f:
                    f.write(f"{doi}\n")
        except Exception as e:
            # Log to console if writing to file fails
            logger.error(f"Failed to write to fail_log: {e}", extra={"event": "fail_log_error"})

    def _submit_tasks(self) -> dict[Future[Any], str]:
        self.executor = ThreadPoolExecutor(max_workers=self.settings.get("max_workers", 10))
        return {
            self.executor.submit(
                self.downloader.download_one, doi, self._cancel_event
            ): doi
            for doi in self.dois
        }

    def _process_completed_future(self, future: Future[Any], doi: str) -> tuple[int, int, int]:
        success, skipped, failed = 0, 0, 0
        try:
            result = future.result()
            status = result.get("status", "failed")

            if status == "success":
                success = 1
            elif status == "skipped":
                skipped = 1
            else:
                failed = 1
                self._log_failure(result.get("doi", doi))

            self.progress_queue.put(result)

        except CancelledError:
            failed = 1
            self._log_failure(doi)
            self.progress_queue.put(
                {"status": "error", "doi": doi, "message": "Task was cancelled"}
            )
        except Exception as e:
            failed = 1
            self._log_failure(doi)
            self.progress_queue.put(
                {"status": "error", "doi": doi, "message": f"Error: {e}"}
            )
        return success, skipped, failed

    def _handle_cancellation(self, pending_futures: set[Future[Any]], success: int, skipped: int, failed: int):
        failed += len(pending_futures)
        for remaining_future in pending_futures:
            self._log_failure(self.future_map.get(remaining_future, "Unknown DOI"))

        summary_msg = f"Success: {success}\nSkipped: {skipped}\nFailed: {failed}"
        self.progress_queue.put({"status": "cancelled", "message": summary_msg})

    def _handle_completion(self, success: int, skipped: int, failed: int):
        summary_msg = f"Success: {success}\nSkipped: {skipped}\nFailed: {failed}"
        self.progress_queue.put({"status": "complete", "message": summary_msg})

    def _process_batch(self, pending_futures: set[Future[Any]]) -> tuple[int, int, int]:
        success, skipped, failed = 0, 0, 0
        try:
            for future in as_completed(pending_futures, timeout=0.5):
                pending_futures.remove(future)
                doi = self.future_map.get(future, "Unknown DOI")
                s, sk, f = self._process_completed_future(future, doi)
                success += s
                skipped += sk
                failed += f

                if self._cancel_event.is_set():
                    break
        except TimeoutError:
            pass
        return success, skipped, failed

    def _process_futures_loop(self, pending_futures: set[Future[Any]]) -> tuple[int, int, int]:
        success, skipped, failed = 0, 0, 0
        while pending_futures:
            if self._cancel_event.is_set():
                break

            s, sk, f = self._process_batch(pending_futures)
            success += s
            skipped += sk
            failed += f
            
        return success, skipped, failed

    def run(self):
        """Runs the entire download process in this worker thread."""
        op_id = start_operation()
        logger.info(f"Starting download manager run for DOIs: {self.dois}", extra={"event": "download_manager_start"})
        self._cancel_event.clear()
        
        try:
            self.progress_queue.put(
                {"status": "start", "message": "--- Starting Download ---"}
            )
            self.future_map = self._submit_tasks()
            pending_futures = set(self.future_map.keys())

            success, skipped, failed = self._process_futures_loop(pending_futures)

            if self._cancel_event.is_set():
                self._handle_cancellation(pending_futures, success, skipped, failed)
            else:
                self._handle_completion(success, skipped, failed)

        except Exception as e:
            for doi in self.dois:
                self._log_failure(doi)
            self.progress_queue.put(
                {"status": "critical_error", "message": f"Manager error: {e}"}
            )

        finally:
            if self.executor:
                self.executor.shutdown(wait=True, cancel_futures=True)
            self.executor = None
            self.future_map = {}
            self.progress_queue.put({"status": "finished"})

    def cancel_download(self):
        """Signals the download process to stop."""
        self._cancel_event.set()
        if self.future_map:
            for future in self.future_map.keys():
                future.cancel()
