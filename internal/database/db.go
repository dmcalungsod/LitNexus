package database

import (
	"database/sql"
	"fmt"
	"log"
	"time"

	"litnexus/internal/domain"

	_ "modernc.org/sqlite"
)

type Manager struct {
	db *sql.DB
}

func NewManager(dbPath string) (*Manager, error) {
	if dbPath == "" {
		dbPath = "workspace.db"
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open sqlite database at %s: %w", dbPath, err)
	}

	// Enforce single connection for SQLite writes to avoid locking issues
	db.SetMaxOpenConns(1)

	m := &Manager{db: db}
	if err := m.initDB(); err != nil {
		return nil, err
	}

	return m, nil
}

func (m *Manager) Close() error {
	return m.db.Close()
}

func (m *Manager) initDB() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS papers (
			doi TEXT PRIMARY KEY,
			title TEXT,
			authors TEXT,
			year INTEGER,
			abstract TEXT,
			pdf_status TEXT DEFAULT 'pending',
			generation INTEGER DEFAULT 0,
			local_filepath TEXT,
			external_reference_count INTEGER,
			external_citation_count INTEGER,
			external_counts_source TEXT,
			external_counts_fetched_at TEXT,
			references_fetch_status TEXT,
			citations_fetch_status TEXT
		)`,
		`CREATE TABLE IF NOT EXISTS edges (
			source_doi TEXT,
			target_doi TEXT,
			PRIMARY KEY (source_doi, target_doi),
			FOREIGN KEY (source_doi) REFERENCES papers (doi),
			FOREIGN KEY (target_doi) REFERENCES papers (doi)
		)`,
		`CREATE TABLE IF NOT EXISTS paper_discoveries (
			paper_doi TEXT,
			source_doi TEXT,
			direction TEXT,
			generation INTEGER,
			discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			PRIMARY KEY (paper_doi, source_doi, direction)
		)`,
		`CREATE TABLE IF NOT EXISTS sessions (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			seed_identifier TEXT,
			date_started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			target_depth INTEGER DEFAULT 1
		)`,
	}

	for _, query := range queries {
		if _, err := m.db.Exec(query); err != nil {
			return fmt.Errorf("db schema initialization failed: %w", err)
		}
	}

	// Migration: Add pdf_status_reason column if missing
	_, _ = m.db.Exec(`ALTER TABLE papers ADD COLUMN pdf_status_reason TEXT`)

	return nil
}

func (m *Manager) AddPaper(p domain.Paper) error {
	query := `INSERT OR IGNORE INTO papers (doi, title, authors, year, abstract, generation, pdf_status, pdf_status_reason)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
	status := p.PDFStatus
	if status == "" {
		status = "pending"
	}
	_, err := m.db.Exec(query, p.DOI, p.Title, p.Authors, p.Year, p.Abstract, p.Generation, status, p.PDFStatusReason)
	return err
}

func (m *Manager) AddEdge(sourceDOI, targetDOI string) error {
	query := `INSERT OR IGNORE INTO edges (source_doi, target_doi) VALUES (?, ?)`
	_, err := m.db.Exec(query, sourceDOI, targetDOI)
	return err
}

func (m *Manager) AddDiscovery(paperDOI, sourceDOI, direction string, generation int) error {
	query := `INSERT OR IGNORE INTO paper_discoveries (paper_doi, source_doi, direction, generation)
	VALUES (?, ?, ?, ?)`
	_, err := m.db.Exec(query, paperDOI, sourceDOI, direction, generation)
	return err
}

func (m *Manager) GetAllPapers() ([]domain.Paper, error) {
	query := `SELECT doi, title, authors, year, abstract, generation, pdf_status, COALESCE(pdf_status_reason, ''),
		COALESCE(local_filepath, ''), COALESCE(external_reference_count, 0), COALESCE(external_citation_count, 0),
		COALESCE(external_counts_source, ''), COALESCE(external_counts_fetched_at, ''),
		COALESCE(references_fetch_status, ''), COALESCE(citations_fetch_status, '')
	FROM papers ORDER BY CASE WHEN generation = 0 THEN 0 ELSE 1 END, generation ASC, year DESC`

	return m.queryPapers(query)
}

func (m *Manager) GetPastReferences(doi string) ([]domain.Paper, error) {
	query := `SELECT p.doi, p.title, p.authors, p.year, p.abstract, p.generation, p.pdf_status, COALESCE(p.pdf_status_reason, ''),
		COALESCE(p.local_filepath, ''), COALESCE(p.external_reference_count, 0), COALESCE(p.external_citation_count, 0),
		COALESCE(p.external_counts_source, ''), COALESCE(p.external_counts_fetched_at, ''),
		COALESCE(p.references_fetch_status, ''), COALESCE(p.citations_fetch_status, '')
	FROM papers p
	JOIN edges e ON p.doi = e.target_doi
	WHERE e.source_doi = ?`

	return m.queryPapers(query, doi)
}

func (m *Manager) GetFutureCitations(doi string) ([]domain.Paper, error) {
	query := `SELECT p.doi, p.title, p.authors, p.year, p.abstract, p.generation, p.pdf_status, COALESCE(p.pdf_status_reason, ''),
		COALESCE(p.local_filepath, ''), COALESCE(p.external_reference_count, 0), COALESCE(p.external_citation_count, 0),
		COALESCE(p.external_counts_source, ''), COALESCE(p.external_counts_fetched_at, ''),
		COALESCE(p.references_fetch_status, ''), COALESCE(p.citations_fetch_status, '')
	FROM papers p
	JOIN edges e ON p.doi = e.source_doi
	WHERE e.target_doi = ?`

	return m.queryPapers(query, doi)
}

func (m *Manager) UpdatePDFStatus(doi, status, localFilepath, statusReason string) error {
	query := `UPDATE papers SET pdf_status = ?, local_filepath = ?, pdf_status_reason = ? WHERE doi = ?`
	_, err := m.db.Exec(query, status, localFilepath, statusReason, doi)
	return err
}

func (m *Manager) UpdateCounts(doi string, refCount, citCount int, source string) error {
	now := time.Now().UTC().Format(time.RFC3339)
	query := `UPDATE papers SET external_reference_count = ?, external_citation_count = ?, external_counts_source = ?, external_counts_fetched_at = ? WHERE doi = ?`
	_, err := m.db.Exec(query, refCount, citCount, source, now, doi)
	return err
}

func (m *Manager) queryPapers(query string, args ...interface{}) ([]domain.Paper, error) {
	rows, err := m.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var papers []domain.Paper
	for rows.Next() {
		var p domain.Paper
		err := rows.Scan(
			&p.DOI, &p.Title, &p.Authors, &p.Year, &p.Abstract, &p.Generation, &p.PDFStatus, &p.PDFStatusReason,
			&p.LocalFilepath, &p.ExternalReferenceCount, &p.ExternalCitationCount,
			&p.ExternalCountsSource, &p.ExternalCountsFetchedAt,
			&p.ReferencesFetchStatus, &p.CitationsFetchStatus,
		)
		if err != nil {
			log.Printf("Error scanning paper: %v", err)
			continue
		}
		papers = append(papers, p)
	}
	return papers, nil
}

func (m *Manager) DeletePaper(doi string) error {
	_, _ = m.db.Exec(`DELETE FROM edges WHERE source_doi = ? OR target_doi = ?`, doi, doi)
	_, _ = m.db.Exec(`DELETE FROM paper_discoveries WHERE paper_doi = ? OR source_doi = ?`, doi, doi)
	_, err := m.db.Exec(`DELETE FROM papers WHERE doi = ?`, doi)
	return err
}

func (m *Manager) ClearAll() error {
	tables := []string{"papers", "edges", "paper_discoveries", "sessions"}
	for _, table := range tables {
		if _, err := m.db.Exec(fmt.Sprintf("DELETE FROM %s", table)); err != nil {
			return err
		}
	}
	return nil
}
