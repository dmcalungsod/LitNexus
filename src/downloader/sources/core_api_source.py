from src.downloader.logging_config import get_logger, start_operation
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)

class CoreApiSource(Source):
    def __init__(self, session: requests.Session, api_key: str | None):
        super().__init__(session)
        self.api_key = api_key
        self.api_url = config.CORE_API_URL

    def _get_data(self, doi: str):
        if not self.api_key: return None
        try:
            url = self.api_url.format(doi=quote_plus(doi))
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = self._make_request(url, headers=headers, timeout=10)
            if resp and resp.status_code == 200: return resp.json()
        except Exception as e:
            logger.error(f"[{self.name}] Failed to get data for DOI {doi}: {e}", exc_info=True)
        return None

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        data = self._get_data(doi)
        if not data: return None
        return {
            "year": str(data.get("year", "Unknown")),
            "title": data.get("title", "Unknown Title"),
            "authors": [a.get("name") for a in data.get("authors", [])],
            "doi": data.get("doi", doi),
            "_pdf_url": data.get("fullTextLink")
        }

    def download(self, doi: str, filepath, metadata: dict[str, Any]) -> bool:
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            data = self._get_data(doi)
            pdf_url = data.get("fullTextLink") if data else None
        if pdf_url and ("pdf" in pdf_url.lower()):
            return self._fetch_and_save(pdf_url, filepath)
        return False