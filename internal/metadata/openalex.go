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

type OpenAlexSource struct {
	client *http.Client
}

func NewOpenAlexSource(verifySSL bool) *OpenAlexSource {
	return &OpenAlexSource{client: defaultHTTPClient(verifySSL)}
}

func (o *OpenAlexSource) Name() string {
	return "OpenAlex"
}

type openAlexResponse struct {
	Title           string `json:"title"`
	PublicationYear int    `json:"publication_year"`
	Authorships     []struct {
		Author struct {
			DisplayName string `json:"display_name"`
		} `json:"author"`
	} `json:"authorships"`
	OpenAccess struct {
		OAURL string `json:"oa_url"`
	} `json:"open_access"`
}

func (o *OpenAlexSource) FetchMetadata(ctx context.Context, doi string) (*domain.Metadata, error) {
	reqURL := fmt.Sprintf(config.OpenAlexAPIURL, url.QueryEscape(doi))
	req, err := newHTTPRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	resp, err := o.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("openalex returned status %d", resp.StatusCode)
	}

	var res openAlexResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, err
	}

	var authors []string
	for _, a := range res.Authorships {
		if a.Author.DisplayName != "" {
			authors = append(authors, a.Author.DisplayName)
		}
	}

	return &domain.Metadata{
		DOI:     doi,
		Title:   res.Title,
		Year:    res.PublicationYear,
		Authors: authors,
		PDFURL:  res.OpenAccess.OAURL,
		Source:  o.Name(),
	}, nil
}
