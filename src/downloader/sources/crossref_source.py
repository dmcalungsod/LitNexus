# downloader/crossref_source.py
"""
Defines the source for Crossref.
"""
from src.downloader.logging_config import get_logger, start_operation
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)


class CrossrefSource(Source):
    """
    A source for finding metadata from Crossref.
    """

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.CROSSREF_API_URL
        self._metadata_cache: dict[str, dict[str, Any] | None] = {}

    @staticmethod
    def _extract_year(message: dict) -> str | None:
        """Extracts the publication year from the message."""
        def _get_year_from_parts(parts):
            if parts and isinstance(parts, list) and len(parts) > 0:
                first_part = parts[0]
                if first_part and isinstance(first_part, list) and len(first_part) > 0:
                    return first_part[0]
            return None

        if "published-print" in message:
            if year := _get_year_from_parts(message["published-print"].get("date-parts")):
                return year
        if "published-online" in message:
            if year := _get_year_from_parts(message["published-online"].get("date-parts")):
                return year
        if "issued" in message:
            if year := _get_year_from_parts(message["issued"].get("date-parts")):
                return year
        return None

    @staticmethod
    def _extract_authors(message: dict) -> list[str]:
        """Extracts and normalizes author names."""
        authors = []
        for author in message.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            full_name = f"{given} {family}".strip()
            if full_name:
                authors.append(full_name)
        return authors

    @staticmethod
    def _parse_metadata(message: dict) -> dict[str, Any]:
        """Parse Crossref API response into standard metadata format."""
        titles = message.get("title")
        title = titles[0] if titles and isinstance(titles, list) else "Unknown Title"
        
        year = CrossrefSource._extract_year(message)
        authors = CrossrefSource._extract_authors(message)

        return {
            "title": title,
            "year": str(year) if year else "Unknown",
            "authors": authors,
        }

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets the metadata for a given DOI from the Crossref API.
        Results are cached in-memory to avoid redundant API calls.
        
        API Compliance: Respects Crossref rate limits (1 req/sec implicit via 2-sec intervals).
        """
        if doi in self._metadata_cache:
            return self._metadata_cache[doi]
        
        try:
            # --- MODIFIED: URL-encode the DOI ---
            search_url = f"{self.api_url}works/{quote_plus(doi)}"
            response = self._make_request(search_url)
            if not response:
                self._metadata_cache[doi] = None
                return None

            data = response.json()
            logger.debug(f"[{self.name}] Full response for {doi}: {data}")
            if data.get("status") != "ok":
                logger.debug(f"[{self.name}] No results found for DOI: {doi}")
                self._metadata_cache[doi] = None
                return None

            message = data.get("message", {})
            logger.debug(f"[{self.name}] Message for {doi}: {message}")

            result = self._parse_metadata(message)
            result["doi"] = doi
            self._metadata_cache[doi] = result
            return result

        except (requests.RequestException, ValueError) as e:
            logger.warning(f"[{self.name}] Metadata request failed for {doi}: {e}")
            self._metadata_cache[doi] = None
            return None

    def download(self, doi: str, filepath: Path, metadata: dict[str, Any]) -> bool:
        """
        This source only provides metadata, so it does not download anything.
        """
        return False
