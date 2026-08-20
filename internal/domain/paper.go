package domain

import "time"

// Paper represents an academic paper/article in the LitNexus workspace.
type Paper struct {
	DOI                     string    `json:"doi"`
	Title                   string    `json:"title"`
	Authors                 string    `json:"authors"`
	Year                    int       `json:"year"`
	Abstract                string    `json:"abstract,omitempty"`
	Generation              int       `json:"generation"`
	PDFStatus               string    `json:"pdf_status"`
	PDFStatusReason         string    `json:"pdf_status_reason,omitempty"`
	LocalFilepath           string    `json:"local_filepath,omitempty"`
	ExternalReferenceCount  int       `json:"external_reference_count"`
	ExternalCitationCount   int       `json:"external_citation_count"`
	ExternalCountsSource    string    `json:"external_counts_source,omitempty"`
	ExternalCountsFetchedAt string    `json:"external_counts_fetched_at,omitempty"`
	ReferencesFetchStatus   string    `json:"references_fetch_status,omitempty"`
	CitationsFetchStatus    string    `json:"citations_fetch_status,omitempty"`
}

// Edge represents a directional citation relationship between two papers (Source cited Target).
type Edge struct {
	SourceDOI string `json:"source_doi"`
	TargetDOI string `json:"target_doi"`
}

// PaperDiscovery records how a paper was discovered (provenance/lineage).
type PaperDiscovery struct {
	PaperDOI     string    `json:"paper_doi"`
	SourceDOI    string    `json:"source_doi"`
	Direction    string    `json:"direction"` // "reference" or "citation"
	Generation   int       `json:"generation"`
	DiscoveredAt time.Time `json:"discovered_at"`
	SourceTitle  string    `json:"source_title,omitempty"`
}

// DownloadResult summarizes the outcome of a PDF download attempt.
type DownloadResult struct {
	DOI      string `json:"doi"`
	Status   string `json:"status"` // "success", "failed", "skipped"
	Source   string `json:"source,omitempty"`
	Filename string `json:"filename,omitempty"`
	Error    string `json:"error,omitempty"`
}

// Metadata holds raw or enriched metadata fetched from open-access sources.
type Metadata struct {
	DOI       string   `json:"doi"`
	Title     string   `json:"title"`
	Year      int      `json:"year"`
	Authors   []string `json:"authors"`
	Abstract  string   `json:"abstract,omitempty"`
	PDFURL    string   `json:"pdf_url,omitempty"`
	Source    string   `json:"source,omitempty"`
}
