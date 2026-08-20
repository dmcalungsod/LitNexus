package metadata

import (
	"context"
	"sync"
	"time"

	"litnexus/internal/domain"
)

type Fetcher struct {
	sources []Source
}

func NewFetcher(unpaywallEmail string, verifySSL bool) *Fetcher {
	return &Fetcher{
		sources: []Source{
			NewCrossrefSource(verifySSL),
			NewUnpaywallSource(unpaywallEmail, verifySSL),
			NewOpenAlexSource(verifySSL),
			NewSemanticScholarSource(verifySSL),
		},
	}
}

// FetchParallel queries all metadata sources concurrently for a given DOI.
func (f *Fetcher) FetchParallel(ctx context.Context, doi string) (*domain.Metadata, string) {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()

	type result struct {
		meta   *domain.Metadata
		source string
		err    error
	}

	ch := make(chan result, len(f.sources))
	var wg sync.WaitGroup

	for _, s := range f.sources {
		wg.Add(1)
		go func(src Source) {
			defer wg.Done()
			meta, err := src.FetchMetadata(ctx, doi)
			ch <- result{meta: meta, source: src.Name(), err: err}
		}(s)
	}

	go func() {
		wg.Wait()
		close(ch)
	}()

	var bestMeta *domain.Metadata
	var primaryPDFURL string

	highConfidence := map[string]bool{
		"Crossref":  true,
		"Unpaywall": true,
	}

	for res := range ch {
		if res.err == nil && res.meta != nil {
			if res.meta.PDFURL != "" && primaryPDFURL == "" {
				primaryPDFURL = res.meta.PDFURL
			}

			if bestMeta == nil {
				bestMeta = res.meta
			} else {
				// Enrich missing attributes
				if bestMeta.Title == "" || bestMeta.Title == "Unknown Title" {
					bestMeta.Title = res.meta.Title
				}
				if bestMeta.Year == 0 {
					bestMeta.Year = res.meta.Year
				}
				if len(bestMeta.Authors) == 0 {
					bestMeta.Authors = res.meta.Authors
				}
				if bestMeta.Abstract == "" {
					bestMeta.Abstract = res.meta.Abstract
				}
			}

			// Early return if high confidence source succeeded with valid title
			if highConfidence[res.source] && bestMeta.Title != "" && bestMeta.Title != "Unknown Title" {
				break
			}
		}
	}

	return bestMeta, primaryPDFURL
}
