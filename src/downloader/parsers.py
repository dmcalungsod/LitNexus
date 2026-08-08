# downloader/parsers.py
"""Functions to extract DOIs from various academic citation file formats."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import bibtexparser
import defusedxml.ElementTree as ET
import rispy

from .utils import clean_doi
from .pdf_extractor import extract_dois_from_pdf

DOI_REGEX = r"\b(10[.]\d{4,9}/[-._;()/:A-Z0-9]+)\b"


def _parse_generic(text: str, loader: Callable[[str], Any], key: str = "doi") -> list[str]:
    """Generic parser for structured formats."""
    dois = set()
    try:
        data = loader(text)
        # Handle both list of dicts (RIS, JSON) and object with entries (BibTeX)
        items = data.entries if hasattr(data, "entries") else data
        for item in items:
            val = item.get(key)
            if val and (cleaned := clean_doi(val)):
                dois.add(cleaned)
    except Exception:
        pass
    return list(dois)


def _parse_bibtex(text: str) -> list[str]:
    """Extracts DOIs from a BibTeX string."""
    return _parse_generic(text, bibtexparser.loads, "doi")


def _parse_ris(text: str) -> list[str]:
    """Extracts DOIs from an RIS string using the rispy library."""
    return _parse_generic(text, rispy.loads, "doi")


def _parse_endnote_xml(text: str) -> list[str]:
    """Extracts DOIs from an EndNote XML string."""
    dois = set()
    try:
        root = ET.fromstring(text)
        for doi_node in root.findall(".//electronic-resource-num"):
            if doi_node.text and (cleaned := clean_doi(doi_node.text)):
                dois.add(cleaned)
    except Exception:
        pass
    return list(dois)


def _parse_json(text: str) -> list[str]:
    """Extracts DOIs from a Zotero-style JSON export."""
    return _parse_generic(text, json.loads, "DOI")


def _parse_plain_text(text: str) -> list[str]:
    """Finds all DOIs in a plain text or CSV string using regex."""
    dois = set()
    for match in re.findall(DOI_REGEX, text, re.IGNORECASE):
        if cleaned := clean_doi(match):
            dois.add(cleaned)
    return list(dois)


def _detect_parser_from_content(text: str) -> Callable[[str], list[str]]:
    """Detects the appropriate parser based on file content."""
    if "TY  -" in text and "ER  -" in text:
        return _parse_ris
    elif "@article" in text.lower() or "@book" in text.lower():
        return _parse_bibtex
    return _parse_plain_text


def extract_dois_from_file(filepath: str) -> list[str]:
    """
    Reads a file and extracts DOIs based on its content and extension.
    Supports .bib, .ris, .xml, .enw, .txt, .csv, .json, and .pdf.
    """
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = p.suffix.lower()

    if ext == ".pdf":
        return extract_dois_from_pdf(filepath)

    text = p.read_text(encoding="utf-8", errors="ignore")

    parser_map = {
        ".bib": _parse_bibtex,
        ".ris": _parse_ris,
        ".xml": _parse_endnote_xml,
        ".enw": _parse_endnote_xml,
        ".json": _parse_json,
    }

    if ext in parser_map:
        dois = parser_map[ext](text)
    elif ext in [".txt", ".csv"]:
        parser = _detect_parser_from_content(text)
        dois = parser(text)
    else:
        dois = _parse_plain_text(text)

    return sorted(list(set(dois)))
