package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	runtimeos "runtime"
	"strings"
	"sync"

	"litnexus/internal/database"
	"litnexus/internal/domain"
	"litnexus/internal/downloader"
	"litnexus/internal/metadata"
	"litnexus/internal/parsers"
	"litnexus/internal/settings"
	"litnexus/internal/snowball"
	"litnexus/internal/utils"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct holds application state and exposes Go methods to Wails JS frontend.
type App struct {
	ctx            context.Context
	db             *database.Manager
	settingsMgr    *settings.Manager
	downloader     *downloader.Downloader
	snowballEngine *snowball.Engine
	fetcher        *metadata.Fetcher
}

// NewApp creates a new App application struct.
func NewApp() *App {
	return &App{}
}

// startup is called when Wails initializes the application context.
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx

	sm, err := settings.NewManager()
	if err != nil {
		fmt.Printf("Failed to initialize settings manager: %v\n", err)
	}
	a.settingsMgr = sm
	st := sm.GetSettings()

	db, err := database.NewManager("workspace.db")
	if err != nil {
		fmt.Printf("Failed to initialize SQLite database: %v\n", err)
	}
	a.db = db

	a.downloader = downloader.NewDownloader(st.OutputDirectory, st.UnpaywallEmail, st.VerifySSL)
	a.downloader.SetProxy(st.InstitutionalProxy)
	a.snowballEngine = snowball.NewEngine(db, st.UnpaywallEmail, st.VerifySSL)
	a.fetcher = metadata.NewFetcher(st.UnpaywallEmail, st.VerifySSL)
}

// AddDOI adds a single DOI to the workspace, fetching its metadata online.
func (a *App) AddDOI(rawDOI string) (*domain.Paper, error) {
	doi := utils.CleanDOI(rawDOI)
	if doi == "" {
		return nil, fmt.Errorf("invalid DOI string")
	}

	meta, _ := a.fetcher.FetchParallel(a.ctx, doi)
	if meta == nil {
		meta = &domain.Metadata{DOI: doi, Title: "Unknown Title"}
	}

	authorStr := utils.FormatAuthorsAPA(meta.Authors)
	p := domain.Paper{
		DOI:        doi,
		Title:      meta.Title,
		Authors:    authorStr,
		Year:       meta.Year,
		Abstract:   meta.Abstract,
		Generation: 0,
		PDFStatus:  "pending",
	}

	if err := a.db.AddPaper(p); err != nil {
		return nil, err
	}

	return &p, nil
}

// ImportFile extracts DOIs from a citation file (.bib, .ris, .xml, .json, .csv, .txt) and adds them.
func (a *App) ImportFile(path string) ([]string, error) {
	dois, err := parsers.ExtractDOIsFromFile(path)
	if err != nil {
		return nil, err
	}

	for _, doi := range dois {
		_, _ = a.AddDOI(doi)
	}

	return dois, nil
}

// SelectAndImportFile opens OS native file picker and imports DOIs from selected citation file.
func (a *App) SelectAndImportFile() ([]string, error) {
	filePath, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Import Citation File",
		Filters: []runtime.FileFilter{
			{
				DisplayName: "Citation Files (*.bib, *.ris, *.xml, *.json, *.txt, *.csv)",
				Pattern:     "*.bib;*.ris;*.xml;*.json;*.txt;*.csv",
			},
		},
	})
	if err != nil || filePath == "" {
		return nil, err
	}
	return a.ImportFile(filePath)
}

// GetAllPapers returns all papers currently in the workspace database.
func (a *App) GetAllPapers() ([]domain.Paper, error) {
	return a.db.GetAllPapers()
}

// GetPastReferences retrieves local past references for a given paper.
func (a *App) GetPastReferences(doi string) ([]domain.Paper, error) {
	return a.db.GetPastReferences(doi)
}

// GetFutureCitations retrieves local future citations for a given paper.
func (a *App) GetFutureCitations(doi string) ([]domain.Paper, error) {
	return a.db.GetFutureCitations(doi)
}

// FetchPastReferences triggers literature snowballing to fetch past references for seed paper online.
func (a *App) FetchPastReferences(doi string, generation int) ([]domain.Paper, error) {
	return a.snowballEngine.FetchReferences(a.ctx, doi, generation)
}

// FetchFutureCitations triggers literature snowballing to fetch future citations for seed paper online.
func (a *App) FetchFutureCitations(doi string, generation int) ([]domain.Paper, error) {
	return a.snowballEngine.FetchCitations(a.ctx, doi, generation)
}

// DownloadPDF downloads a single PDF for a given DOI.
func (a *App) DownloadPDF(doi string) (domain.DownloadResult, error) {
	runtime.EventsEmit(a.ctx, "download-start", map[string]interface{}{"doi": doi})
	res := a.downloader.DownloadOne(a.ctx, doi)
	targetPath := ""
	if res.Status == "downloaded" || res.Status == "skipped" {
		targetPath = filepath.Join(a.settingsMgr.GetSettings().OutputDirectory, res.Filename)
	}
	_ = a.db.UpdatePDFStatus(doi, res.Status, targetPath, res.Error)
	runtime.EventsEmit(a.ctx, "download-complete", res)
	return res, nil
}

// DownloadBatchPDFs downloads a slice of DOIs concurrently with real-time progress events.
func (a *App) DownloadBatchPDFs(dois []string) ([]domain.DownloadResult, error) {
	total := len(dois)
	var completed int32
	var mu sync.Mutex

	runtime.EventsEmit(a.ctx, "batch-download-start", map[string]interface{}{
		"total": total,
		"dois":  dois,
	})

	results := a.downloader.DownloadBatch(a.ctx, dois, 4, func(res domain.DownloadResult) {
		mu.Lock()
		completed++
		currCompleted := completed
		mu.Unlock()

		targetPath := ""
		if res.Status == "downloaded" || res.Status == "skipped" {
			targetPath = filepath.Join(a.settingsMgr.GetSettings().OutputDirectory, res.Filename)
		}
		_ = a.db.UpdatePDFStatus(res.DOI, res.Status, targetPath, res.Error)

		percent := 100
		if total > 0 {
			percent = int(float64(currCompleted) / float64(total) * 100)
		}

		runtime.EventsEmit(a.ctx, "batch-download-progress", map[string]interface{}{
			"doi":       res.DOI,
			"status":    res.Status,
			"completed": currCompleted,
			"total":     total,
			"percent":   percent,
			"error":     res.Error,
			"filename":  res.Filename,
		})
	})

	runtime.EventsEmit(a.ctx, "batch-download-complete", map[string]interface{}{
		"results": results,
		"total":   total,
	})
	return results, nil
}

// OpenPDFFile opens a downloaded PDF using OS viewer, or falls back to publisher browser URL.
func (a *App) OpenPDFFile(path string) error {
	if path == "" {
		return fmt.Errorf("file path is empty")
	}

	st := a.settingsMgr.GetSettings()
	fullPath := path
	if !filepath.IsAbs(fullPath) {
		fullPath = filepath.Join(st.OutputDirectory, path)
	}

	// 1. Direct file check
	if fi, err := os.Stat(fullPath); err == nil && !fi.IsDir() {
		return openFileOS(fullPath)
	}

	// 2. Search output directory for PDF matching DOI
	doiClean := strings.ReplaceAll(path, "/", "_")
	if entries, err := os.ReadDir(st.OutputDirectory); err == nil {
		for _, entry := range entries {
			if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".pdf") {
				if strings.Contains(entry.Name(), doiClean) || strings.Contains(entry.Name(), path) {
					matched := filepath.Join(st.OutputDirectory, entry.Name())
					return openFileOS(matched)
				}
			}
		}
	}

	// 3. Fallback: Open publisher DOI page in default web browser
	doiURL := path
	if !strings.HasPrefix(doiURL, "http") {
		doiURL = "https://doi.org/" + path
	}
	runtime.BrowserOpenURL(a.ctx, doiURL)
	return nil
}

// CopyToClipboard copies string content to native system clipboard.
func (a *App) CopyToClipboard(text string) error {
	return runtime.ClipboardSetText(a.ctx, text)
}

// ReadClipboard reads current text from system clipboard.
func (a *App) ReadClipboard() (string, error) {
	return runtime.ClipboardGetText(a.ctx)
}

// GenerateFormattedCitation generates a citation string according to the specified style (APA, MLA, Chicago, Harvard, IEEE, Vancouver, RIS, BibTeX).
func (a *App) GenerateFormattedCitation(doi, title, authors string, year int, style string) string {
	return utils.FormatCitationByStyle(doi, title, authors, year, style)
}

// GenerateAPACitation generates an APA 7th style citation string for a paper.
func (a *App) GenerateAPACitation(doi, title, authors string, year int) string {
	return utils.FormatCitationByStyle(doi, title, authors, year, "APA")
}

// GenerateBibTeX generates a clean BibTeX entry for a paper.
func (a *App) GenerateBibTeX(doi, title, authors string, year int) string {
	return utils.FormatBibTeX(doi, title, authors, year)
}

// GenerateRIS generates a RIS reference entry for a paper.
func (a *App) GenerateRIS(doi, title, authors string, year int) string {
	return utils.FormatRIS(doi, title, authors, year)
}

// ExportWorkspaceBibTeX exports all papers in workspace to a single BibTeX string.
func (a *App) ExportWorkspaceBibTeX() (string, error) {
	papers, err := a.db.GetAllPapers()
	if err != nil {
		return "", err
	}
	var entries []string
	for _, p := range papers {
		entries = append(entries, a.GenerateBibTeX(p.DOI, p.Title, p.Authors, p.Year))
	}
	return strings.Join(entries, "\n\n"), nil
}

// DeletePaper removes a single paper and its relationships from workspace database.
func (a *App) DeletePaper(rawDOI string) error {
	doi := utils.CleanDOI(rawDOI)
	if doi == "" {
		return fmt.Errorf("invalid DOI string")
	}
	return a.db.DeletePaper(doi)
}

// ClearWorkspace removes all papers and citation relationships from workspace database.
func (a *App) ClearWorkspace() error {
	return a.db.ClearAll()
}

// GetSettings loads application configuration settings.
func (a *App) GetSettings() (settings.AppSettings, error) {
	return a.settingsMgr.GetSettings(), nil
}

// SaveSettings updates and saves application configuration settings.
func (a *App) SaveSettings(s settings.AppSettings) error {
	err := a.settingsMgr.Save(s)
	if err == nil {
		a.downloader = downloader.NewDownloader(s.OutputDirectory, s.UnpaywallEmail, s.VerifySSL)
		a.downloader.SetProxy(s.InstitutionalProxy)
		a.fetcher = metadata.NewFetcher(s.UnpaywallEmail, s.VerifySSL)
		a.snowballEngine = snowball.NewEngine(a.db, s.UnpaywallEmail, s.VerifySSL)
	}
	return err
}

// shutdown is called when the Wails application is shutting down.
func (a *App) shutdown(ctx context.Context) {
	if a.db != nil {
		_ = a.db.Close()
	}
}

// openFileOS opens a local file using the OS default application (Windows, macOS, Linux).
func openFileOS(targetPath string) error {
	switch goos := runtimeos.GOOS; goos {
	case "windows":
		return exec.Command("cmd", "/c", "start", "", targetPath).Run()
	case "darwin":
		return exec.Command("open", targetPath).Run()
	default: // linux, freebsd, etc.
		return exec.Command("xdg-open", targetPath).Run()
	}
}
