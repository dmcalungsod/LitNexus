from src.downloader.logging_config import get_logger, start_operation
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)

class SemanticScholarSource(Source):
    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.SEMANTIC_SCHOLAR_API_URL

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        try:
            url = config.SEMANTIC_SCHOLAR_API_URL.format(doi=quote_plus(doi))
            resp = self._make_request(url, timeout=10)
            if not resp or resp.status_code != 200: return None
            data = resp.json()
            return {
                "year": str(data.get("year", "Unknown")),
                "title": data.get("title", "Unknown Title"),
                "authors": [a.get("name") for a in data.get("authors", [])],
                "doi": doi,
                "_pdf_url": (data.get("openAccessPdf") or {}).get("url") or data.get("pdfUrl")
            }
        except Exception: return None

    def download(self, doi: str, filepath, metadata: dict[str, Any]) -> bool:
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None
        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False