# downloader/zenodo_source.py
"""
Defines the source for Zenodo.
"""
from src.downloader.logging_config import get_logger, start_operation
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)


class ZenodoSource(Source):
    """
    A source for finding open access articles from Zenodo.
    """

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.ZENODO_API_URL

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets the metadata for a given DOI from the Zenodo API.
        """
        try:
            # --- MODIFIED: URL-encode the DOI in the query ---
            search_url = f'{self.api_url}records?q=doi:"{quote_plus(doi)}"'
            response = self._make_request(search_url)
            if not response:
                return None

            data = response.json()
            if data.get("hits", {}).get("total", 0) == 0:
                logger.debug(f"[{self.name}] No results found for DOI: {doi}")
                return None

            # The first result is the most likely match
            result = data.get("hits", {}).get("hits", [])[0]
            metadata = result.get("metadata", {})

            title = metadata.get("title", "Unknown Title")
            pub_date = metadata.get("publication_date", "Unknown")
            year = pub_date.split("-")[0] if pub_date and "-" in pub_date else "Unknown"

            # Find the PDF URL
            pdf_url = None
            for f in result.get("files", []):
                if f.get("mimetype") == "application/pdf":
                    pdf_url = f.get("links", {}).get("self")
                    break

            authors = [creator.get("name") for creator in metadata.get("creators", [])]

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
        Downloads the PDF for a given DOI from Zenodo.
        """
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            # If _pdf_url is not in the provided metadata, try to get fresh metadata
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None

        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False
