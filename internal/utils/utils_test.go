package utils

import (
	"testing"
)

func TestCleanDOI(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"https://doi.org/10.1038/s41586-020-2649-2", "10.1038/s41586-020-2649-2"},
		{"http://dx.doi.org/10.1016/j.cell.2021.01.001.", "10.1016/j.cell.2021.01.001"},
		{"10.1000/182", "10.1000/182"},
		{"invalid_doi", ""},
	}

	for _, tt := range tests {
		got := CleanDOI(tt.input)
		if got != tt.expected {
			t.Errorf("CleanDOI(%q) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestFormatAuthorsAPA(t *testing.T) {
	tests := []struct {
		authors  []string
		expected string
	}{
		{[]string{"Albert Einstein"}, "Einstein"},
		{[]string{"Albert Einstein", "Niels Bohr"}, "Einstein & Bohr"},
		{[]string{"Albert Einstein", "Niels Bohr", "Max Planck"}, "Einstein et al."},
		{[]string{}, "Unknown Author"},
	}

	for _, tt := range tests {
		got := FormatAuthorsAPA(tt.authors)
		if got != tt.expected {
			t.Errorf("FormatAuthorsAPA(%v) = %q; want %q", tt.authors, got, tt.expected)
		}
	}
}

func TestFormatCitationByStyle(t *testing.T) {
	doi := "10.1038/s41586-020-2649-2"
	title := "Quantum supremacy using a programmable superconducting processor"
	authors := "Arute, F., Arya, K., Babbush, R."
	year := 2019

	apa := FormatCitationByStyle(doi, title, authors, year, "APA")
	if apa == "" || !testing.Verbose() {
		// Just ensure non-empty valid string output
	}

	styles := []string{"APA", "MLA", "Chicago", "Harvard", "IEEE", "Vancouver", "BibTeX", "RIS"}
	for _, style := range styles {
		got := FormatCitationByStyle(doi, title, authors, year, style)
		if got == "" {
			t.Errorf("FormatCitationByStyle for style %s returned empty string", style)
		}
	}
}

