package config

const (
	MaxFilenameLen        = 200
	UnpaywallAPIURL       = "https://api.unpaywall.org/v2/%s"
	OpenAlexAPIURL        = "https://api.openalex.org/works/https://doi.org/%s"
	SemanticScholarAPIURL = "https://api.semanticscholar.org/graph/v1/paper/DOI:%s"
	CoreAPIURL            = "https://api.core.ac.uk/v3/works/doi:%s"
	ArxivAPIURL           = "http://export.arxiv.org/api/query"
	ArxivPDFURL           = "https://arxiv.org/pdf/%s.pdf"
	DOIResolverURL        = "https://doi.org/%s"
	PubMedAPIURL          = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
	DOAJAPIURL            = "https://doaj.org/api/v2/"
	ZenodoAPIURL          = "https://zenodo.org/api/"
	OSFAPIURL             = "https://api.osf.io/v2/"
	CrossrefAPIURL        = "https://api.crossref.org/"
	DefaultUserAgent      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
