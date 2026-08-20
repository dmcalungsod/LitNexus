package metadata

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"

	"litnexus/internal/config"
	"litnexus/internal/domain"
)

type SemanticScholarSource struct {
	client *http.Client
}

func NewSemanticScholarSource(verifySSL bool) *SemanticScholarSource {
	return &SemanticScholarSource{client: defaultHTTPClient(verifySSL)}
}

func (s *SemanticScholarSource) Name() string {
	return "SemanticScholar"
}

type semanticScholarResponse struct {
	Title    string `json:"title"`
	Year     int    `json:"year"`
	Abstract string `json:"abstract"`
	Authors  []struct {
		Name string `json:"name"`
	} `json:"authors"`
	OpenAccessPdf struct {
		URL string `json:"url"`
	} `json:"openAccessPdf"`
}

func (s *SemanticScholarSource) FetchMetadata(ctx context.Context, doi string) (*domain.Metadata, error) {
	reqURL := fmt.Sprintf("%s?fields=title,year,authors,abstract,openAccessPdf", fmt.Sprintf(config.SemanticScholarAPIURL, url.QueryEscape(doi)))
	req, err := newHTTPRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("semantic scholar returned status %d", resp.StatusCode)
	}

	var res semanticScholarResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, err
	}

	var authors []string
	for _, a := range res.Authors {
		if a.Name != "" {
			authors = append(authors, a.Name)
		}
	}

	return &domain.Metadata{
		DOI:      doi,
		Title:    res.Title,
		Year:     res.Year,
		Authors:  authors,
		Abstract: res.Abstract,
		PDFURL:   res.OpenAccessPdf.URL,
		Source:   s.Name(),
	}, nil
}
