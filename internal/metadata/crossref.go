package metadata

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strings"

	"litnexus/internal/config"
	"litnexus/internal/domain"
)

var xmlTagRegex = regexp.MustCompile(`<[^>]*>`)

func stripXMLTags(s string) string {
	return strings.TrimSpace(xmlTagRegex.ReplaceAllString(s, ""))
}

type CrossrefSource struct {
	client *http.Client
}

func NewCrossrefSource(verifySSL bool) *CrossrefSource {
	return &CrossrefSource{client: defaultHTTPClient(verifySSL)}
}

func (c *CrossrefSource) Name() string {
	return "Crossref"
}

type crossrefResponse struct {
	Status  string `json:"status"`
	Message struct {
		Title  []string `json:"title"`
		Author []struct {
			Given  string `json:"given"`
			Family string `json:"family"`
		} `json:"author"`
		PublishedPrint  dateParts `json:"published-print"`
		PublishedOnline dateParts `json:"published-online"`
		Issued          dateParts `json:"issued"`
		Abstract        string    `json:"abstract"`
		Link            []struct {
			URL         string `json:"URL"`
			ContentType string `json:"content-type"`
		} `json:"link"`
	} `json:"message"`
}

type dateParts struct {
	DateParts [][]int `json:"date-parts"`
}

func (dp *dateParts) Year() int {
	if len(dp.DateParts) > 0 && len(dp.DateParts[0]) > 0 {
		return dp.DateParts[0][0]
	}
	return 0
}

func (c *CrossrefSource) FetchMetadata(ctx context.Context, doi string) (*domain.Metadata, error) {
	reqURL := fmt.Sprintf("%sworks/%s", config.CrossrefAPIURL, url.QueryEscape(doi))
	req, err := newHTTPRequest(ctx, reqURL)
	if err != nil {
		return nil, err
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("crossref returned status %d", resp.StatusCode)
	}

	var res crossrefResponse
	if err := json.NewDecoder(resp.Body).Decode(&res); err != nil {
		return nil, err
	}

	if res.Status != "ok" {
		return nil, fmt.Errorf("crossref status not ok")
	}

	title := "Unknown Title"
	if len(res.Message.Title) > 0 {
		title = res.Message.Title[0]
	}

	year := res.Message.PublishedPrint.Year()
	if year == 0 {
		year = res.Message.PublishedOnline.Year()
	}
	if year == 0 {
		year = res.Message.Issued.Year()
	}

	var authors []string
	for _, a := range res.Message.Author {
		fullName := fmt.Sprintf("%s %s", a.Given, a.Family)
		if fullName != " " {
			authors = append(authors, fullName)
		}
	}

	abstract := stripXMLTags(res.Message.Abstract)

	var pdfURL string
	for _, link := range res.Message.Link {
		if strings.Contains(link.ContentType, "application/pdf") && link.URL != "" {
			pdfURL = link.URL
			break
		}
	}

	return &domain.Metadata{
		DOI:      doi,
		Title:    title,
		Year:     year,
		Authors:  authors,
		Abstract: abstract,
		PDFURL:   pdfURL,
		Source:   c.Name(),
	}, nil
}
