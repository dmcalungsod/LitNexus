package downloader

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"litnexus/internal/config"
	"litnexus/internal/domain"
	"litnexus/internal/metadata"
	"litnexus/internal/utils"
)

type Downloader struct {
	fetcher            *metadata.Fetcher
	outputDir          string
	institutionalProxy string
	client             *http.Client
}

func NewDownloader(outputDir string, unpaywallEmail string, verifySSL bool) *Downloader {
	if outputDir == "" {
		home, _ := os.UserHomeDir()
		outputDir = filepath.Join(home, "Downloads", "LitNexus_PDFs")
	}
	_ = os.MkdirAll(outputDir, 0755)

	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: !verifySSL},
	}

	return &Downloader{
		fetcher:   metadata.NewFetcher(unpaywallEmail, verifySSL),
		outputDir: outputDir,
		client: &http.Client{
			Timeout:   45 * time.Second,
			Transport: tr,
		},
	}
}

func (d *Downloader) SetOutputDir(dir string) {
	d.outputDir = dir
	_ = os.MkdirAll(dir, 0755)
}

func (d *Downloader) SetProxy(proxy string) {
	d.institutionalProxy = strings.TrimSpace(proxy)
}

func GenerateFilename(meta *domain.Metadata) string {
	title := "Unknown Title"
	if meta.Title != "" {
		title = meta.Title
	}
	yearStr := "Unknown"
	if meta.Year > 0 {
		yearStr = strconv.Itoa(meta.Year)
	}

	authorStr := utils.FormatAuthorsAPA(meta.Authors)
	doiPart := strings.ReplaceAll(meta.DOI, "/", "_")

	var parts []string
	if authorStr != "Unknown Author" && yearStr != "Unknown" {
		parts = append(parts, fmt.Sprintf("%s, %s", authorStr, yearStr))
	} else if authorStr != "Unknown Author" {
		parts = append(parts, authorStr)
	} else if yearStr != "Unknown" {
		parts = append(parts, yearStr)
	}

	if title != "Unknown Title" {
		parts = append(parts, title)
	}
	parts = append(parts, doiPart)

	baseName := utils.SafeFilename(strings.Join(parts, " - "))
	return baseName + ".pdf"
}

func (d *Downloader) DownloadOne(ctx context.Context, doi string) domain.DownloadResult {
	meta, pdfURL := d.fetcher.FetchParallel(ctx, doi)
	if meta == nil {
		meta = &domain.Metadata{DOI: doi}
	}

	filename := GenerateFilename(meta)
	targetPath := filepath.Join(d.outputDir, filename)

	// Check if already downloaded
	if fi, err := os.Stat(targetPath); err == nil && fi.Size() > 5000 {
		return domain.DownloadResult{
			DOI:      doi,
			Status:   "skipped",
			Source:   "local_cache",
			Filename: filename,
		}
	}

	if pdfURL == "" {
		// No open access PDF URL found from any metadata source
		if d.institutionalProxy == "" {
			return domain.DownloadResult{
				DOI:      doi,
				Status:   "failed",
				Filename: filename,
				Error:    "No open-access PDF URL available from metadata providers (Crossref, Unpaywall, OpenAlex, Semantic Scholar). Configure an Institutional Proxy in Settings or download from publisher.",
			}
		}
	}

	var lastErr error
	if pdfURL != "" {
		err := d.downloadFile(ctx, pdfURL, targetPath)
		if err == nil {
			return domain.DownloadResult{
				DOI:      doi,
				Status:   "downloaded",
				Source:   meta.Source,
				Filename: filename,
			}
		}
		lastErr = err
	}

	// Institutional Proxy Fallback Channel
	if d.institutionalProxy != "" {
		proxyTarget := d.institutionalProxy
		if !strings.HasSuffix(proxyTarget, "url=") && !strings.HasSuffix(proxyTarget, "=") {
			proxyTarget += "https://doi.org/"
		}
		if !strings.Contains(proxyTarget, doi) {
			proxyTarget += doi
		}

		proxyErr := d.downloadFile(ctx, proxyTarget, targetPath)
		if proxyErr == nil {
			return domain.DownloadResult{
				DOI:      doi,
				Status:   "downloaded",
				Source:   "institutional_proxy",
				Filename: filename,
			}
		}
		if lastErr == nil {
			lastErr = proxyErr
		}
	}

	errReason := "No open-access PDF available for this DOI."
	if lastErr != nil {
		errReason = lastErr.Error()
	}

	return domain.DownloadResult{
		DOI:      doi,
		Status:   "failed",
		Filename: filename,
		Error:    errReason,
	}
}

func (d *Downloader) downloadFile(ctx context.Context, url, dest string) error {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", config.DefaultUserAgent)
	req.Header.Set("Accept", "application/pdf,text/html;q=0.9,*/*;q=0.8")

	resp, err := d.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("HTTP status %d", resp.StatusCode)
	}

	tmpPath := dest + ".part"
	outFile, err := os.Create(tmpPath)
	if err != nil {
		return err
	}

	_, err = io.Copy(outFile, resp.Body)
	_ = outFile.Close()
	if err != nil {
		_ = os.Remove(tmpPath)
		return err
	}

	// Validate PDF file size
	fi, err := os.Stat(tmpPath)
	if err != nil || fi.Size() < 5000 {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("downloaded file invalid or too small (%d bytes)", fi.Size())
	}

	// Validate PDF Header (%PDF-)
	f, err := os.Open(tmpPath)
	if err == nil {
		header := make([]byte, 5)
		_, _ = f.Read(header)
		_ = f.Close()
		if string(header) != "%PDF-" {
			_ = os.Remove(tmpPath)
			return fmt.Errorf("response content is not valid PDF binary")
		}
	}

	return os.Rename(tmpPath, dest)
}

func (d *Downloader) DownloadBatch(ctx context.Context, dois []string, concurrency int, onProgress func(res domain.DownloadResult)) []domain.DownloadResult {
	if concurrency <= 0 {
		concurrency = 3
	}

	sem := make(chan struct{}, concurrency)
	results := make([]domain.DownloadResult, len(dois))
	var wg sync.WaitGroup

	for i, doi := range dois {
		wg.Add(1)
		go func(idx int, targetDOI string) {
			defer wg.Done()
			sem <- struct{}{}
			res := d.DownloadOne(ctx, targetDOI)
			<-sem

			results[idx] = res
			if onProgress != nil {
				onProgress(res)
			}
		}(i, doi)
	}

	wg.Wait()
	return results
}
