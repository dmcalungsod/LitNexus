# src/downloader/core.py
from src.downloader.logging_config import get_logger, start_operation
import random
import threading
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config
from .download_pipeline import DownloadPipeline
from .source_manager import SourceManager

logger = get_logger(__name__)

class Downloader:
    """Manages the PDF download pipeline and metadata orchestration."""

    def __init__(
        self,
        output_dir: str,
        email: str,
        core_api_key: str | None,
        verify_ssl: bool = True,
        openalex_api_key: str | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.email = email
        self.verify_ssl = verify_ssl
        self.session = self._create_session()
        self.stats: dict[str, Any] = {"success": 0, "fail": 0, "skipped": 0, "sources": {}}
        self._stats_lock = threading.Lock()

        self.source_manager = SourceManager(self.session, self.email, core_api_key, openalex_api_key)
        self.pipeline = DownloadPipeline(
            self.source_manager,
            self.output_dir,
            self.stats,
            self._stats_lock
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers["User-Agent"] = random.choice(config.USER_AGENTS)
        session.verify = self.verify_ssl
        if not self.verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning("SSL verification disabled.")

        retries = Retry(total=5, backoff_factor=1, status_forcelist=[408, 429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def download_one(self, doi: str, cancel_event: threading.Event | None = None) -> dict[str, Any]:
        """Runs full download pipeline for one DOI with cancel support."""
        return self.pipeline.download_one(doi, cancel_event)

    def test_connections(self):
        return self.source_manager.test_connections()
