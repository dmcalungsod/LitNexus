import re
from pathlib import Path
from pypdf import PdfReader
from src.downloader.utils import clean_doi
from src.downloader.logging_config import get_logger

logger = get_logger(__name__)

DOI_REGEX = r"\b(10[.]\d{4,9}/[-._;()/:A-Z0-9]+)\b"

def extract_dois_from_pdf(filepath: str) -> list[str]:
    """
    Extracts DOIs from a PDF file using pypdf.
    It scans both the raw text and the URI annotations for DOIs.
    """
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    dois = set()
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            # 1. Extract from Text
            try:
                text = page.extract_text()
                if text:
                    for match in re.findall(DOI_REGEX, text, re.IGNORECASE):
                        if cleaned := clean_doi(match):
                            dois.add(cleaned)
            except Exception as e:
                logger.debug(f"Error extracting text from page: {e}")

            # 2. Extract from URI Annotations
            try:
                if "/Annots" in page:
                    for annot_ref in page["/Annots"]:
                        annot = annot_ref.get_object()
                        if annot.get("/Subtype") == "/Link" and "/A" in annot:
                            action = annot["/A"].get_object()
                            if action.get("/S") == "/URI" and "/URI" in action:
                                uri = action["/URI"]
                                # Search for DOI pattern in the URL
                                for match in re.findall(DOI_REGEX, uri, re.IGNORECASE):
                                    if cleaned := clean_doi(match):
                                        dois.add(cleaned)
            except Exception as e:
                logger.debug(f"Error extracting annotations from page: {e}")

    except Exception as e:
        logger.error(f"Failed to process PDF {filepath}: {e}")

    return sorted(list(dois))
