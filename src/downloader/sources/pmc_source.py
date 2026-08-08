from src.downloader.logging_config import get_logger, start_operation
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ParseError

import defusedxml.ElementTree as ET
import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)


class PubMedCentralSource(Source):
    """
    A source for downloading PDFs from PubMed Central.
    """

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.PUBMED_API_URL

    def _get_pmcid_from_doi(self, doi: str) -> str | None:
        """Resolves a DOI to a PMCID using ESearch."""
        esearch_url = f"{self.api_url}esearch.fcgi"
        params = {
            "db": "pmc",
            "term": f"{doi}[DOI]",
            "retmode": "json",
        }
        response = self._make_request(esearch_url, params=params)
        if not response:
            return None

        data = response.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            logger.debug(f"[{self.name}] No PMCID found for DOI: {doi}")
            return None
        return id_list[0]

    def _fetch_metadata_xml(self, pmcid: str) -> Element | None:
        """Fetches metadata XML for a given PMCID using EFetch."""
        efetch_url = f"{self.api_url}efetch.fcgi"
        params = {
            "db": "pmc",
            "id": pmcid,
            "retmode": "xml",
        }
        response = self._make_request(efetch_url, params=params)
        if not response:
            return None
        try:
            return ET.fromstring(response.content)
        except (ParseError, ValueError):
            return None

    def _parse_metadata_xml(self, root: Element, doi: str, pmcid: str) -> dict[str, Any]:
        """Parses the metadata XML to extract title, year, authors, etc."""
        title = root.findtext(".//article-title") or "Unknown Title"
        year = root.findtext(".//pub-date/year") or "Unknown"
        resolved_doi = root.findtext(".//article-id[@pub-id-type='doi']") or doi
        authors = [
            author.text.strip()
            for author in root.findall(".//contrib[@contrib-type='author']/name/surname")
            if author.text and author.text.strip()
        ]

        return {
            "title": title,
            "year": year,
            "authors": authors,
            "doi": resolved_doi,
            "pmcid": pmcid,
        }

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        """
        Gets the metadata for a given DOI from PubMed Central.
        """
        try:
            pmcid = self._get_pmcid_from_doi(doi)
            if not pmcid:
                return None

            root = self._fetch_metadata_xml(pmcid)
            if root is None:
                return None

            return self._parse_metadata_xml(root, doi, pmcid)

        except (requests.RequestException, ValueError, ParseError) as e:
            logger.warning(f"[{self.name}] Metadata request failed for {doi}: {e}")
            return None

    def download(self, doi: str, filepath: Path, metadata: dict[str, Any]) -> bool:
        """
        Downloads the PDF for a given DOI from PubMed Central.
        """
        pmcid = metadata.get("pmcid")
        if not pmcid:
            logger.debug(f"[{self.name}] No PMCID found in metadata for DOI: {doi}")
            return False

        try:
            # Use the PMC OA Web Service API to get the download link
            oa_url = f"{self.api_url}oa.fcgi"
            params = {"id": pmcid}
            response = self._make_request(oa_url, params=params)
            if not response:
                return False

            # Parse the XML response to find the PDF download link
            root = ET.fromstring(response.content)
            pdf_link = root.find(".//link[@format='pdf']")
            if pdf_link is None or not pdf_link.get("href"):
                logger.debug(f"[{self.name}] No PDF link found for PMCID: {pmcid}")
                return False

            pdf_url = pdf_link.get("href")
            if pdf_url:
                return self._fetch_and_save(pdf_url, filepath)
            return False

        except (requests.RequestException, ParseError) as e:
            logger.warning(f"[{self.name}] Download failed for {doi}: {e}")
            return False
