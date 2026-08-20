package utils

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	doiURLPrefixRegex = regexp.MustCompile(`(?i)^https?://(dx\.)?doi\.org/`)
	doiPatternRegex   = regexp.MustCompile(`^10\.\d{4,9}/.+$`)
	safeFilenameRegex = regexp.MustCompile(`[<>:"/\\|?*\n\r\t]+`)
	safeCharsRegex    = regexp.MustCompile(`[^A-Za-z0-9 _\-\.\(\)\[\],&]+`)
	doiExtractRegex   = regexp.MustCompile(`(?i)\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b`)
)

const MaxFilenameLength = 200

// CleanDOI sanitizes and validates a DOI string.
func CleanDOI(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}

	cleaned := doiURLPrefixRegex.ReplaceAllString(raw, "")
	cleaned = strings.TrimRight(cleaned, ".,;})] ")

	if doiPatternRegex.MatchString(cleaned) {
		return cleaned
	}
	return ""
}

// ExtractDOIsFromText finds all valid DOIs in a text snippet.
func ExtractDOIsFromText(text string) []string {
	matches := doiExtractRegex.FindAllString(text, -1)
	seen := make(map[string]bool)
	var result []string

	for _, m := range matches {
		if cleaned := CleanDOI(m); cleaned != "" {
			if !seen[cleaned] {
				seen[cleaned] = true
				result = append(result, cleaned)
			}
		}
	}
	return result
}

// SafeFilename creates a cross-platform safe filename from text.
func SafeFilename(text string) string {
	text = safeFilenameRegex.ReplaceAllString(text, "_")
	text = safeCharsRegex.ReplaceAllString(text, "")
	text = strings.TrimSpace(text)
	if len(text) > MaxFilenameLength {
		text = text[:MaxFilenameLength]
	}
	return text
}

// FormatAuthorsAPA converts a slice of author names to APA 7th style surname string.
func FormatAuthorsAPA(authors []string) string {
	if len(authors) == 0 {
		return "Unknown Author"
	}

	var surnames []string
	for _, author := range authors {
		trimmed := strings.TrimSpace(author)
		if trimmed == "" {
			continue
		}
		parts := strings.Fields(trimmed)
		if len(parts) > 0 {
			surnames = append(surnames, parts[len(parts)-1])
		}
	}

	if len(surnames) == 0 {
		return "Unknown Author"
	}
	if len(surnames) == 1 {
		return surnames[0]
	}
	if len(surnames) == 2 {
		return surnames[0] + " & " + surnames[1]
	}
	return surnames[0] + " et al."
}

// FormatCitationByStyle generates formatted citation strings for various academic styles.
func FormatCitationByStyle(doi, title, authors string, year int, style string) string {
	if authors == "" {
		authors = "Unknown Author"
	}
	if title == "" {
		title = "Unknown Title"
	}
	yearStr := "n.d."
	if year > 0 {
		yearStr = fmt.Sprintf("%d", year)
	}
	doiClean := CleanDOI(doi)
	if doiClean == "" {
		doiClean = doi
	}

	switch strings.ToUpper(strings.TrimSpace(style)) {
	case "MLA", "MLA 9TH":
		return fmt.Sprintf("%s. \"%s.\" %s. https://doi.org/%s.", authors, title, yearStr, doiClean)
	case "CHICAGO", "CHICAGO 17TH":
		return fmt.Sprintf("%s. \"%s.\" (%s). https://doi.org/%s.", authors, title, yearStr, doiClean)
	case "HARVARD":
		return fmt.Sprintf("%s (%s) '%s'. Available at: https://doi.org/%s.", authors, yearStr, title, doiClean)
	case "IEEE":
		return fmt.Sprintf("%s, \"%s,\" %s, doi: %s.", authors, title, yearStr, doiClean)
	case "VANCOUVER":
		return fmt.Sprintf("%s. %s. %s; Available from: https://doi.org/%s.", authors, title, yearStr, doiClean)
	case "RIS":
		return FormatRIS(doiClean, title, authors, year)
	case "BIBTEX":
		return FormatBibTeX(doiClean, title, authors, year)
	case "APA", "APA 7TH":
		fallthrough
	default:
		return fmt.Sprintf("%s (%s). %s. https://doi.org/%s", authors, yearStr, title, doiClean)
	}
}

// FormatBibTeX generates a clean BibTeX entry for a paper.
func FormatBibTeX(doi, title, authors string, year int) string {
	parts := strings.Split(doi, "/")
	key := "article"
	if len(parts) > 1 {
		key = parts[len(parts)-1]
	}
	yearStr := "n.d."
	if year > 0 {
		yearStr = fmt.Sprintf("%d", year)
	}
	if title == "" {
		title = "Unknown Title"
	}
	if authors == "" {
		authors = "Unknown Author"
	}
	return fmt.Sprintf("@article{%s,\n  title = {%s},\n  author = {%s},\n  year = {%s},\n  doi = {%s},\n  url = {https://doi.org/%s}\n}", key, title, authors, yearStr, doi, doi)
}

// FormatRIS generates a RIS reference entry for a paper.
func FormatRIS(doi, title, authors string, year int) string {
	yearStr := ""
	if year > 0 {
		yearStr = fmt.Sprintf("%d", year)
	}
	if title == "" {
		title = "Unknown Title"
	}
	if authors == "" {
		authors = "Unknown Author"
	}

	var sb strings.Builder
	sb.WriteString("TY  - JOUR\n")
	sb.WriteString(fmt.Sprintf("TI  - %s\n", title))
	authorList := strings.Split(authors, ",")
	for _, a := range authorList {
		a = strings.TrimSpace(a)
		if a != "" {
			sb.WriteString(fmt.Sprintf("AU  - %s\n", a))
		}
	}
	if yearStr != "" {
		sb.WriteString(fmt.Sprintf("PY  - %s\n", yearStr))
	}
	if doi != "" {
		sb.WriteString(fmt.Sprintf("DO  - %s\n", doi))
		sb.WriteString(fmt.Sprintf("UR  - https://doi.org/%s\n", doi))
	}
	sb.WriteString("ER  -")
	return sb.String()
}

