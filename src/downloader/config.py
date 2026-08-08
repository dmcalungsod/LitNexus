# downloader/config.py
"""Configuration constants for the downloader."""

MAX_FILENAME_LEN = 200

USER_AGENTS = [
    # Modern mainstream desktop browsers to reduce bot-blocking risks
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/127.0.0.0 Chrome/127.0.0.0 Safari/537.36",
]

UNPAYWALL_API_URL = "https://api.unpaywall.org/v2/{doi}"
OPENALEX_API_URL = "https://api.openalex.org/works/https://doi.org/{doi}"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
CORE_API_URL = "https://api.core.ac.uk/v3/works/doi:{doi}"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}.pdf"
DOI_RESOLVER_URL = "https://doi.org/{doi}"
PUBMED_API_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
DOAJ_API_URL = "https://doaj.org/api/v2/"
ZENODO_API_URL = "https://zenodo.org/api/"
OSF_API_URL = "https://api.osf.io/v2/"
CROSSREF_API_URL = "https://api.crossref.org/"
