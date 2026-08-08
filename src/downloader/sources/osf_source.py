# downloader/osf_source.py
"""
Defines the source for the Open Science Framework (OSF).
"""
from src.downloader.logging_config import get_logger, start_operation
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)


class OSFSource(Source):
    """
    A source for finding open access articles from the OSF.
    """

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.OSF_API_URL

    def _parse_creator_name(self, creator: dict[str, Any]) -> str | None:
        """Parses a single creator object to extract the name."""
        c_attrs = creator.get("attributes", creator)
        full_name = c_attrs.get("full_name")
        given = c_attrs.get("given_name", "")
        family = c_attrs.get("family_name", "")
        return full_name or f"{given} {family}".strip() or None

    def _extract_authors(self, attributes: dict[str, Any]) -> list[str]:
        """Extracts author names from the attributes."""
        raw_creators = attributes.get("creators", [])
        authors = []
        for creator in raw_creators:
            name = self._parse_creator_name(creator)
            if name:
                authors.append(name)
        return authors

    def _fetch_metadata_json(self, doi: str) -> dict[str, Any] | None:
        """Fetches metadata JSON from OSF API."""
        search_url = f"{self.api_url}search/?q={quote_plus(doi)}"
        response = self._make_request(search_url)
        if not response:
            return None

        data = response.json()
        if data.get("meta", {}).get("total", 0) == 0:
            logger.debug(f"[{self.name}] No results found for DOI: {doi}")
            return None
        return data

    def _parse_metadata(self, data: dict[str, Any], doi: str) -> dict[str, Any]:
        """Parses the OSF metadata response."""
        # The first result is the most likely match
        data_list = data.get("data") or []
        if not data_list:
            attributes = {}
            title = "Unknown Title"
            year = "Unknown"
            result = {}
        else:
            result = data_list[0]
            attributes = result.get("attributes", {})
            title = attributes.get("title", "Unknown Title")
            date_published = attributes.get("date_published")
            if isinstance(date_published, str) and date_published and "-" in date_published:
                year = date_published.split("-")[0]
            else:
                year = "Unknown"

        # Find the PDF URL
        pdf_url = None
        links = result.get("links", {})
        if "download" in links:
            pdf_url = links.get("download")

        authors = self._extract_authors(attributes)

        return {
            "title": title,
            "year": year,
            "authors": authors,
            "doi": doi,
            "_pdf_url": pdf_url,
        }

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets the metadata for a given DOI from the OSF API.
        """
        try:
            data = self._fetch_metadata_json(doi)
            if not data:
                return None

            return self._parse_metadata(data, doi)

        except (requests.RequestException, ValueError) as e:
            logger.warning(f"[{self.name}] Metadata request failed for {doi}: {e}")
            return None



    def download(self, doi: str, filepath: Path, metadata: dict[str, Any]) -> bool:
        """
        Downloads the PDF for a given DOI from the OSF.
        """
        pdf_url = metadata.get("_pdf_url")
        if not pdf_url:
            # If _pdf_url is not in the provided metadata, try to get fresh metadata
            meta = self.get_metadata(doi)
            pdf_url = meta.get("_pdf_url") if meta else None

        if pdf_url:
            return self._fetch_and_save(pdf_url, filepath)
        return False
