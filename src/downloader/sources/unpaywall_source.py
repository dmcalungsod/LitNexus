from src.downloader.logging_config import get_logger, start_operation
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)

class UnpaywallSource(Source):
    def __init__(self, session: requests.Session, email: str):
        super().__init__(session)
        self.email = email
        self.api_url = config.UNPAYWALL_API_URL

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        if not self.email:
            logger.warning(f"[{self.name}] Email not configured, skipping Unpaywall.")
            return None
        try:
            url = config.UNPAYWALL_API_URL.format(doi=quote_plus(doi))
            response = self._make_request(url, params={"email": self.email}, timeout=10)
            if not response: return None
            data = response.json()
            
            authors = []
            for a in data.get("z_authors", []):
                given = a.get("given", "").strip()
                family = a.get("family", "").strip()
                full_name = f"{given} {family}".strip()
                if full_name:
                    authors.append(full_name)

            best_oa = data.get("best_oa_location") or {}
            
            return {
                "year": str(data.get("year", "Unknown")),
                "title": data.get("title", "Unknown Title"),
                "authors": authors,
                "doi": doi,
                "_pdf_url": best_oa.get("url_for_pdf")
            }
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning(f"[{self.name}] Unpaywall error for {doi}: {e}")
            return None

    def download(self, doi: str, filepath, metadata: dict[str, Any]) -> bool:
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None
        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False

    def test_connection(self):
        if not self.email: return (False, "Email not configured")
        return super().test_connection()