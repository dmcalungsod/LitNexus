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

type UnpaywallSource struct {
	client *http.Client
	email  string
}

func NewUnpaywallSource(email string, verifySSL bool) *UnpaywallSource {
	return &UnpaywallSource{client: defaultHTTPClient(verifySSL), email: email}
}

func (u *UnpaywallSource) Name() string {
	return "Unpaywall"
}

type unpaywallResponse struct {
	Title    string `json:"title"`
	Year     int    `json:"year"`
	ZAuthors []struct {
		Given  string `json:"given"`
		Family string `json:"family"`
	} `json:"z_authors"`
	BestOALocation struct {
		URLForPDF string `json:"url_for_pdf"`
	} `json:"best_oa_location"`
}

func (u *UnpaywallSource) FetchMetadata(ctx context.Context, doi string) (*domain.Metadata, error) {
	if u.email == "" {
		return nil, fmt.Errorf("unpaywall email not configured")
	}

	reqURL := fmt.Sprintf("%s?email=%s", fmt.Sprintf(config.UnpaywallAPIURL, url.QueryEscape(doi)), url.QueryEscape(u.email))
	req, err := newHTTPRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	resp, err := u.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unpaywall returned status %d", resp.StatusCode)
	}

	var res unpaywallResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, err
	}

	var authors []string
	for _, a := range res.ZAuthors {
		fullName := fmt.Sprintf("%s %s", a.Given, a.Family)
		if fullName != " " {
			authors = append(authors, fullName)
		}
	}

	return &domain.Metadata{
		DOI:     doi,
		Title:   res.Title,
		Year:    res.Year,
		Authors: authors,
		PDFURL:  res.BestOALocation.URLForPDF,
		Source:  u.Name(),
	}, nil
}
