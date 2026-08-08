from src.downloader.logging_config import get_logger, start_operation
import re
from typing import Any
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
import requests

from src.downloader import config

from .base import Source

logger = get_logger(__name__)

class ArxivSource(Source):
    ARXIV_DOI_REGEX = r"10\.48550/arXiv\.(\d+\.\d+v?\d*)"
    ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, session: requests.Session):
        super().__init__(session)
        self.api_url = config.ARXIV_API_URL

    def _get_arxiv_id(self, doi: str) -> str | None:
        if m := re.search(self.ARXIV_DOI_REGEX, doi, flags=re.IGNORECASE):
            return m.group(1)
        return None

    def _extract_authors(self, entry: Element) -> list[str]:
        authors = []
        for author_elem in entry.findall('atom:author', self.ATOM_NS):
            name_elem = author_elem.find('atom:name', self.ATOM_NS)
            if name_elem is not None and name_elem.text is not None:
                authors.append(name_elem.text)
        return authors

    def _extract_basic_info(self, entry: Element) -> tuple[str, str] | None:
        published_elem = entry.find("atom:published", self.ATOM_NS)
        title_elem = entry.find("atom:title", self.ATOM_NS)
        if published_elem is None or title_elem is None:
            return None
        
        published_text = published_elem.text
        title_text = title_elem.text
        if published_text is None or title_text is None:
            return None
            
        return published_text, title_text

    def _parse_metadata_from_xml(self, xml_text: str, doi: str) -> dict[str, Any] | None:
        try:
            root = ET.fromstring(xml_text)
            entry = root.find("atom:entry", self.ATOM_NS)
            if entry is None:
                return None
            
            basic_info = self._extract_basic_info(entry)
            if not basic_info:
                return None
            published_text, title_text = basic_info
            
            authors = self._extract_authors(entry)
            
            return {
                "year": published_text.split("-")[0],
                "title": title_text.strip().replace("\n", " "),
                "authors": authors,
                "doi": doi
            }
        except Exception as e:
            logger.error(f"[{self.name}] XML parsing failed for {doi}: {e}", exc_info=True)
            return None

    def get_metadata(self, doi: str) -> dict[str, Any] | None:
        arxiv_id = self._get_arxiv_id(doi)
        if not arxiv_id: return None
        try:
            url = f"{config.ARXIV_API_URL}?id_list={arxiv_id}"
            resp = self._make_request(url, timeout=10)
            if not resp: return None
            
            return self._parse_metadata_from_xml(resp.text, doi)
        except Exception as e:
            logger.error(f"[{self.name}] Metadata request failed for {doi}: {e}", exc_info=True)
            return None

    def download(self, doi: str, filepath, metadata: dict[str, Any]) -> bool:
        arxiv_id = self._get_arxiv_id(doi)
        if arxiv_id:
            return self._fetch_and_save(config.ARXIV_PDF_URL.format(arxiv_id=arxiv_id), filepath)
        return False