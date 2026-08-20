package snowball

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"

	"litnexus/internal/config"
	"litnexus/internal/database"
	"litnexus/internal/domain"
	"litnexus/internal/utils"
)

type Engine struct {
	db     *database.Manager
	client *http.Client
	email  string
}

func NewEngine(db *database.Manager, email string, verifySSL bool) *Engine {
	if email == "" {
		email = "user@litnexus.org"
	}
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: !verifySSL},
	}
	return &Engine{
		db: db,
		client: &http.Client{
			Timeout:   30 * time.Second,
			Transport: tr,
		},
		email: email,
	}
}

type openAlexWork struct {
	ID                    string   `json:"id"`
	DOI                   string   `json:"doi"`
	Title                 string   `json:"title"`
	PublicationYear       int      `json:"publication_year"`
	ReferencedWorks       []string `json:"referenced_works"`
	ReferencedWorksCount int      `json:"referenced_works_count"`
	Authorships           []struct {
		Author struct {
			DisplayName string `json:"display_name"`
		} `json:"author"`
	} `json:"authorships"`
	AbstractInvertedIndex map[string][]int `json:"abstract_inverted_index"`
}

type openAlexListResponse struct {
	Meta struct {
		Count int `json:"count"`
	} `json:"meta"`
	Results []openAlexWork `json:"results"`
}

func parseAbstract(inverted map[string][]int) string {
	if len(inverted) == 0 {
		return ""
	}
	posMap := make(map[int]string)
	var maxPos int
	for word, positions := range inverted {
		for _, pos := range positions {
			posMap[pos] = word
			if pos > maxPos {
				maxPos = pos
			}
		}
	}
	var words []string
	for i := 0; i <= maxPos; i++ {
		if w, ok := posMap[i]; ok {
			words = append(words, w)
		}
	}
	return strings.Join(words, " ")
}

// FetchReferences retrieves past papers cited by seedDOI (generation - 1).
func (e *Engine) FetchReferences(ctx context.Context, seedDOI string, currentGeneration int) ([]domain.Paper, error) {
	reqURL := fmt.Sprintf(config.OpenAlexAPIURL, url.QueryEscape(seedDOI))
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", fmt.Sprintf("LitNexus-Snowball/1.0 (mailto:%s)", e.email))

	resp, err := e.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("openalex returned status %d for %s", resp.StatusCode, seedDOI)
	}

	var seedWork openAlexWork
	if err := json.NewDecoder(resp.Body).Decode(&seedWork); err != nil {
		return nil, err
	}

	if len(seedWork.ReferencedWorks) == 0 {
		return nil, nil
	}

	var shortIDs []string
	for _, w := range seedWork.ReferencedWorks {
		parts := strings.Split(w, "/")
		if len(parts) > 0 {
			shortIDs = append(shortIDs, parts[len(parts)-1])
		}
	}

	batchSize := 50
	childGen := currentGeneration - 1
	var added []domain.Paper

	for i := 0; i < len(shortIDs); i += batchSize {
		end := i + batchSize
		if end > len(shortIDs) {
			end = len(shortIDs)
		}
		batch := shortIDs[i:end]
		filterStr := "openalex:" + strings.Join(batch, "|")
		batchURL := fmt.Sprintf("https://api.openalex.org/works?filter=%s&per-page=%d&select=doi,title,publication_year,authorships,abstract_inverted_index", url.QueryEscape(filterStr), len(batch))

		breq, _ := http.NewRequestWithContext(ctx, "GET", batchURL, nil)
		breq.Header.Set("User-Agent", fmt.Sprintf("LitNexus-Snowball/1.0 (mailto:%s)", e.email))

		bresp, err := e.client.Do(breq)
		if err != nil {
			continue
		}

		var listRes openAlexListResponse
		_ = json.NewDecoder(bresp.Body).Decode(&listRes)
		bresp.Body.Close()

		for _, item := range listRes.Results {
			childDOI := utils.CleanDOI(item.DOI)
			if childDOI == "" {
				continue
			}

			var authorNames []string
			for _, a := range item.Authorships {
				if a.Author.DisplayName != "" {
					authorNames = append(authorNames, a.Author.DisplayName)
				}
			}
			authorsStr := strings.Join(authorNames, ", ")
			abstractStr := parseAbstract(item.AbstractInvertedIndex)

			p := domain.Paper{
				DOI:        childDOI,
				Title:      item.Title,
				Authors:    authorsStr,
				Year:       item.PublicationYear,
				Abstract:   abstractStr,
				Generation: childGen,
				PDFStatus:  "pending",
			}

			_ = e.db.AddPaper(p)
			_ = e.db.AddEdge(seedDOI, childDOI)
			_ = e.db.AddDiscovery(childDOI, seedDOI, "reference", childGen)
			added = append(added, p)
		}
	}

	return added, nil
}

// FetchCitations retrieves future papers citing seedDOI (generation + 1).
func (e *Engine) FetchCitations(ctx context.Context, seedDOI string, currentGeneration int) ([]domain.Paper, error) {
	reqURL := fmt.Sprintf(config.OpenAlexAPIURL, url.QueryEscape(seedDOI))
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", fmt.Sprintf("LitNexus-Snowball/1.0 (mailto:%s)", e.email))

	resp, err := e.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("openalex returned status %d for %s", resp.StatusCode, seedDOI)
	}

	var seedWork openAlexWork
	if err := json.NewDecoder(resp.Body).Decode(&seedWork); err != nil {
		return nil, err
	}

	shortID := seedWork.ID
	parts := strings.Split(shortID, "/")
	if len(parts) > 0 {
		shortID = parts[len(parts)-1]
	}

	citesURL := fmt.Sprintf("https://api.openalex.org/works?filter=cites:%s&select=doi,title,publication_year,authorships,abstract_inverted_index&per-page=50", url.QueryEscape(shortID))
	creq, _ := http.NewRequestWithContext(ctx, "GET", citesURL, nil)
	creq.Header.Set("User-Agent", fmt.Sprintf("LitNexus-Snowball/1.0 (mailto:%s)", e.email))

	cresp, err := e.client.Do(creq)
	if err != nil {
		return nil, err
	}
	defer cresp.Body.Close()

	var listRes openAlexListResponse
	if err := json.NewDecoder(cresp.Body).Decode(&listRes); err != nil {
		return nil, err
	}

	childGen := currentGeneration + 1
	var added []domain.Paper

	for _, item := range listRes.Results {
		childDOI := utils.CleanDOI(item.DOI)
		if childDOI == "" {
			continue
		}

		var authorNames []string
		for _, a := range item.Authorships {
			if a.Author.DisplayName != "" {
				authorNames = append(authorNames, a.Author.DisplayName)
			}
		}
		authorsStr := strings.Join(authorNames, ", ")
		abstractStr := parseAbstract(item.AbstractInvertedIndex)

		p := domain.Paper{
			DOI:        childDOI,
			Title:      item.Title,
			Authors:    authorsStr,
			Year:       item.PublicationYear,
			Abstract:   abstractStr,
			Generation: childGen,
			PDFStatus:  "pending",
		}

		_ = e.db.AddPaper(p)
		_ = e.db.AddEdge(childDOI, seedDOI) // Child cites seed
		_ = e.db.AddDiscovery(childDOI, seedDOI, "citation", childGen)
		added = append(added, p)
	}

	sort.Slice(added, func(i, j int) bool {
		return added[i].Year > added[j].Year
	})

	return added, nil
}
