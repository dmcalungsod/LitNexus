from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from .sources import (
    ArxivSource,
    CoreApiSource,
    CrossrefSource,
    DOAJSource,
    DoiResolverSource,
    OpenAlexSource,
    OSFSource,
    PubMedCentralSource,
    SemanticScholarSource,
    Source,
    UnpaywallSource,
    ZenodoSource,
)


class SourceManager:
    def __init__(self, session: requests.Session, email: str, core_api_key: str | None, openalex_api_key: str | None = None):
        self.session = session
        self.email = email
        self.core_api_key = core_api_key

        # Initialize Sources
        self.core_source = CoreApiSource(self.session, core_api_key)
        self.unpaywall_source = UnpaywallSource(self.session, self.email)
        self.pubmed_central_source = PubMedCentralSource(self.session)
        self.doaj_source = DOAJSource(self.session)
        self.zenodo_source = ZenodoSource(self.session)
        self.osf_source = OSFSource(self.session)
        self.openalex_source = OpenAlexSource(self.session, openalex_api_key)
        self.semantic_scholar_source = SemanticScholarSource(self.session)
        self.arxiv_source = ArxivSource(self.session)
        self.crossref_source = CrossrefSource(self.session)
        self.doi_resolver_source = DoiResolverSource(self.session)

        # Define Pipelines
        self.metadata_sources: list[Source] = [
            self.crossref_source,
            self.unpaywall_source,
            self.core_source,
            self.pubmed_central_source,
            self.doaj_source,
            self.zenodo_source,
            self.osf_source,
            self.arxiv_source,
            self.openalex_source,
            self.semantic_scholar_source,
        ]

        self.pipeline: list[Source] = [
            self.core_source,
            self.unpaywall_source,
            self.pubmed_central_source,
            self.doaj_source,
            self.zenodo_source,
            self.osf_source,
            self.openalex_source,
            self.semantic_scholar_source,
            self.arxiv_source,
            self.doi_resolver_source,
        ]

    def test_connections(self) -> list[dict[str, Any]]:
        results = []
        all_sources_dict = {s.name: s for s in self.metadata_sources + self.pipeline}
        all_sources = list(all_sources_dict.values())

        with ThreadPoolExecutor(max_workers=len(all_sources)) as executor:
            future_map = {executor.submit(s.test_connection): s for s in all_sources}
            for future in as_completed(future_map):
                src = future_map[future]
                try:
                    status, msg = future.result()
                    results.append({"name": src.name, "status": status, "message": msg})
                except Exception as e:
                    results.append(
                        {"name": src.name, "status": False, "message": str(e)}
                    )
        return results
