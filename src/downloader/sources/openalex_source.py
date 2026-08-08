from src.downloader.logging_config import get_logger, start_operation
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)

class OpenAlexSource(Source):
    def __init__(self, session: requests.Session, api_key: str | None = None):
        super().__init__(session)
        self.api_url = config.OPENALEX_API_URL
        self.api_key = api_key
        self._metadata_cache: dict[str, dict[str, Any] | None] = {}

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets metadata from OpenAlex API with in-memory caching.
        
        API Compliance: OpenAlex allows unlimited requests with proper email header.
        Respects our global 2-second rate limit for fairness.
        """
        if doi in self._metadata_cache:
            return self._metadata_cache[doi]
        
        try:
            url = config.OPENALEX_API_URL.format(doi=quote_plus(doi))
            resp = self._make_request(url, timeout=10)
            if not resp:
                self._metadata_cache[doi] = None
                return None
            
            data = resp.json()
            result = {
                "year": str(data.get("publication_year", "Unknown")),
                "title": data.get("title", "Unknown Title"),
                "authors": [a.get("au_name") for a in data.get("authorships", [])],
                "doi": doi,
                "_pdf_url": data.get("open_access", {}).get("oa_url")
            }
            self._metadata_cache[doi] = result
            return result
        except Exception:
            self._metadata_cache[doi] = None
            return None

    def download(self, doi: str, filepath, metadata: dict[str, Any]) -> bool:
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None
        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False