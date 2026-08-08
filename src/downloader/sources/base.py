from src.downloader.logging_config import get_logger, start_operation
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from ..utils import find_pdf_link_on_page

logger = get_logger(__name__)

class Source(ABC):
    """Abstract base class for a PDF source."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.name = self.__class__.__name__.replace("Source", "")
        self._last_request_time = 0.0
        self._min_request_interval = 2.0
        self._lock = threading.Lock()

    @abstractmethod
    def download(self, doi: str, filepath: Path, metadata: dict[str, Any]) -> bool:
        pass

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Retrieves metadata for a DOI. Subclasses can override with caching.
        """
        return None

    def test_connection(self) -> tuple[bool, str]:
        base_url = getattr(self, "api_url", None)
        if base_url:
            try:
                domain = urljoin(base_url, "/")
                r = self.session.get(domain, timeout=5)
                r.raise_for_status()
                return (True, "API is reachable")
            except Exception as e:
                logger.debug(f"[{self.name}] Test ping failed: {e}")
                return (False, "API may be unreachable")
        return (True, "No test implemented")

    def _rate_limit(self) -> None:
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()

    def _write_chunks(self, resp: requests.Response, filepath: Path) -> None:
        with filepath.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)

    def _validate_downloaded_file(self, filepath: Path, content_length: str | None) -> bool:
        file_size = filepath.stat().st_size
        if file_size < 5000:
            logger.warning(f"[{self.name}] File too small ({file_size} bytes).")
            return False
        
        if content_length and abs(file_size - int(content_length)) > 1000:
            logger.warning(f"[{self.name}] File size mismatch.")
        return True

    def _validate_pdf_structure(self, filepath: Path) -> bool:
        file_size = filepath.stat().st_size
        with filepath.open("rb") as fh:
            header = fh.read(1024)
            if not header.startswith(b"%PDF-"):
                logger.warning(f"[{self.name}] Invalid PDF header.")
                return False
            
            seek_pos = max(0, file_size - 1024)
            fh.seek(seek_pos)
            
            if b"%%EOF" not in fh.read(1024):
                logger.warning(f"[{self.name}] Incomplete PDF (missing EOF).")
                return False
        return True

    def _save_stream(self, resp: requests.Response, filepath: Path) -> bool:
        tmp_path = filepath.with_suffix(".part")
        content_length = resp.headers.get("Content-Length")
        content_type = resp.headers.get("Content-Type", "").lower()

        if "application/pdf" not in content_type:
            logger.warning(f"[{self.name}] Content-Type is not PDF ({content_type})")
            return False

        try:
            self._write_chunks(resp, tmp_path)

            if not self._validate_downloaded_file(tmp_path, content_length):
                return False
            
            if not self._validate_pdf_structure(tmp_path):
                return False

            tmp_path.rename(filepath)
            logger.info(f"[{self.name}] Saved PDF: {filepath.name}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Save error: {e}")
            return False
        finally:
            if tmp_path.exists(): tmp_path.unlink()

    def _attempt_direct_download(self, url: str, headers: dict[str, str], filepath: Path) -> bool:
        with self.session.get(url, timeout=30, stream=True, headers=headers) as r:
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "").lower()

            if "application/pdf" in content_type:
                if self._save_stream(r, filepath):
                    return True
        return False

    def _attempt_fallback_download(self, url: str, filepath: Path) -> bool:
        logger.debug(f"[{self.name}] scraping fallback for {url}")
        pdf_url = find_pdf_link_on_page(url, self.session)
        if pdf_url:
            with self.session.get(pdf_url, stream=True, timeout=30) as r2:
                r2.raise_for_status()
                if self._save_stream(r2, filepath):
                    return True
        return False

    def _fetch_and_save(self, url: str, filepath: Path, headers: dict[str, str] | None = None, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                req_headers = dict(self.session.headers)
                req_headers.update({"Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8"})
                if headers:
                    req_headers.update(headers)

                if self._attempt_direct_download(url, req_headers, filepath):
                    return True
                
                # If direct download didn't return True (e.g. not PDF content type), try fallback
                # Note: The original logic tried fallback if content type wasn't PDF.
                # My extracted method returns False if not PDF, so we proceed here.
                # However, we need to be careful not to re-request if we already have the response content...
                # But the original code did a new request inside find_pdf_link_on_page anyway.
                
                if self._attempt_fallback_download(url, filepath):
                    return True

                return False 

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"[{self.name}] Fetch failed: {e}")
                time.sleep((attempt + 1) * 2)
        return False

    def _make_request(self, url: str, method: str = "GET", **kwargs) -> requests.Response | None:
        logger.debug(f"[{self.name}] Making request: {method} {url} {kwargs}")
        try:
            self._rate_limit()
            if "headers" in kwargs:
                merged_headers = dict(self.session.headers)
                merged_headers.update(kwargs["headers"])
                kwargs["headers"] = merged_headers
            
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.debug(f"[{self.name}] Request failed for {url}: {e}")
            return None
