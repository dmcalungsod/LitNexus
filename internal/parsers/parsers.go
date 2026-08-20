package parsers

import (
	"encoding/json"
	"encoding/xml"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"litnexus/internal/utils"
)

var (
	bibtexDOIRegex = regexp.MustCompile(`(?i)doi\s*=\s*[{"]([^}"]+)[}"]`)
	risDOIRegex    = regexp.MustCompile(`(?i)^DO\s*-\s*(.+)$`)
)

// ExtractDOIsFromFile reads a file and extracts all valid DOIs.
func ExtractDOIsFromFile(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file %s: %w", path, err)
	}

	ext := strings.ToLower(filepath.Ext(path))
	text := string(data)

	var dois []string
	switch ext {
	case ".bib":
		dois = parseBibTeX(text)
	case ".ris":
		dois = parseRIS(text)
	case ".xml", ".enw":
		dois = parseEndNoteXML(data)
	case ".json":
		dois = parseJSON(data)
	case ".txt", ".csv":
		dois = parsePlainTextOrAuto(text)
	default:
		dois = utils.ExtractDOIsFromText(text)
	}

	return deduplicateAndSort(dois), nil
}

func parseBibTeX(text string) []string {
	matches := bibtexDOIRegex.FindAllStringSubmatch(text, -1)
	var result []string
	for _, m := range matches {
		if len(m) > 1 {
			if cleaned := utils.CleanDOI(m[1]); cleaned != "" {
				result = append(result, cleaned)
			}
		}
	}

	// Fallback to regex text extraction if bibtex field match was sparse
	if len(result) == 0 {
		result = utils.ExtractDOIsFromText(text)
	}
	return result
}

func parseRIS(text string) []string {
	lines := strings.Split(text, "\n")
	var result []string
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if m := risDOIRegex.FindStringSubmatch(line); len(m) > 1 {
			if cleaned := utils.CleanDOI(m[1]); cleaned != "" {
				result = append(result, cleaned)
			}
		}
	}

	if len(result) == 0 {
		result = utils.ExtractDOIsFromText(text)
	}
	return result
}

type endNoteXMLRecord struct {
	ElectronicResourceNum string `xml:"electronic-resource-num"`
}

type endNoteXMLRoot struct {
	Records []endNoteXMLRecord `xml:"records>record"`
}

func parseEndNoteXML(data []byte) []string {
	var root endNoteXMLRoot
	var result []string
	if err := xml.Unmarshal(data, &root); err == nil {
		for _, rec := range root.Records {
			if cleaned := utils.CleanDOI(rec.ElectronicResourceNum); cleaned != "" {
				result = append(result, cleaned)
			}
		}
	}

	if len(result) == 0 {
		result = utils.ExtractDOIsFromText(string(data))
	}
	return result
}

func parseJSON(data []byte) []string {
	var items []map[string]interface{}
	var result []string

	if err := json.Unmarshal(data, &items); err == nil {
		for _, item := range items {
			for k, v := range item {
				if strings.EqualFold(k, "doi") {
					if strVal, ok := v.(string); ok {
						if cleaned := utils.CleanDOI(strVal); cleaned != "" {
							result = append(result, cleaned)
						}
					}
				}
			}
		}
	}

	if len(result) == 0 {
		result = utils.ExtractDOIsFromText(string(data))
	}
	return result
}

func parsePlainTextOrAuto(text string) []string {
	if strings.Contains(text, "TY  -") && strings.Contains(text, "ER  -") {
		return parseRIS(text)
	}
	if strings.Contains(strings.ToLower(text), "@article") || strings.Contains(strings.ToLower(text), "@book") {
		return parseBibTeX(text)
	}
	return utils.ExtractDOIsFromText(text)
}

func deduplicateAndSort(dois []string) []string {
	seen := make(map[string]bool)
	var unique []string
	for _, d := range dois {
		if !seen[d] {
			seen[d] = true
			unique = append(unique, d)
		}
	}
	sort.Strings(unique)
	return unique
}
