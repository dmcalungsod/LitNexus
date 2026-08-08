# downloader/doaj_source.py
"""
Defines the source for the Directory of Open Access Journals (DOAJ).
"""
from src.downloader.logging_config import get_logger, start_operation
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)


class DOAJSource(Source):
    """
    A source for finding open access articles from the DOAJ.
    """

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.DOAJ_API_URL

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets the metadata for a given DOI from the DOAJ API.
        """
        try:
            # --- MODIFIED: URL-encode the DOI ---
            search_url = f"{self.api_url}search/articles/doi:{quote_plus(doi)}"
            response = self._make_request(search_url)
            if not response:
                return None

            data = response.json()
            if data.get("total", 0) == 0:
                logger.debug(f"[{self.name}] No results found for DOI: {doi}")
                return None

            # The first result is the most likely match
            results = data.get("results") or []
            if not results:
                logger.debug(f"[{self.name}] No results found for DOI: {doi}")
                return None

            result = results[0]
            bibjson = result.get("bibjson", {})

            title = bibjson.get("title", "Unknown Title")
            year = bibjson.get("year", "Unknown")

            # Find the full-text URL
            pdf_url = None
            for identifier in bibjson.get("identifier", []):
                if identifier.get("type") == "fulltext":
                    pdf_url = identifier.get("id")
                    break

            authors = [author.get("name") for author in bibjson.get("author", [])]

            return {
                "title": title,
                "year": year,
                "authors": authors,
                "doi": doi,
                "_pdf_url": pdf_url,
            }

        except (requests.RequestException, ValueError) as e:
            logger.warning(f"[{self.name}] Metadata request failed for {doi}: {e}")
            return None

    def download(self, doi: str, filepath: Path, metadata: dict[str, Any]) -> bool:
        """
        Downloads the PDF for a given DOI from the DOAJ.
        """
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            # If _pdf_url is not in the provided metadata, try to get fresh metadata
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None

        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False
