package metadata

import (
	"context"
	"crypto/tls"
	"net/http"
	"time"

	"litnexus/internal/config"
	"litnexus/internal/domain"
)

type Source interface {
	Name() string
	FetchMetadata(ctx context.Context, doi string) (*domain.Metadata, error)
}

func defaultHTTPClient(verifySSL bool) *http.Client {
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: !verifySSL},
	}
	return &http.Client{
		Timeout:   12 * time.Second,
		Transport: tr,
	}
}

func newHTTPRequest(ctx context.Context, url string) (*http.Request, error) {
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", config.DefaultUserAgent)
	req.Header.Set("Accept", "application/json")
	return req, nil
}
