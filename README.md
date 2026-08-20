# LitNexus

![Last Commit](https://img.shields.io/github/last-commit/dmcalungsod/LitNexus?style=flat-square&cache=none)
![Forks](https://img.shields.io/github/forks/dmcalungsod/LitNexus?style=flat-square&cache=none)
![Issues](https://img.shields.io/github/issues/dmcalungsod/LitNexus?style=flat-square&cache=none)
![Contributors](https://img.shields.io/github/contributors/dmcalungsod/LitNexus?style=flat-square&cache=none)
![Stars](https://img.shields.io/github/stars/dmcalungsod/LitNexus?style=flat-square&cache=none)
![License](https://img.shields.io/github/license/dmcalungsod/LitNexus?style=flat-square&cache=none)
![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-green?style=flat-square)

A modern, open-source desktop application for discovering and downloading open-access academic PDFs using Digital Object Identifiers (DOIs). Built with **Go**, **Wails v2**, **React**, **TypeScript**, and **Tailwind CSS**, LitNexus features a multi-source metadata retrieval pipeline, literature snowballing, and broad citation file format support — all compiled into a single lightweight executable.

> [!WARNING]
> **Development Status**: This application is currently under active development and is not yet production-ready. The system's behavior may be unstable or incomplete, and users may encounter unexpected errors or bugs during operation.

---

## ✨ Key Features

- **Modern Desktop GUI** — A sleek, dark-mode interface with a split-pane layout (data grid + paper preview panel), interactive breadcrumb navigation, multiple theme options, and real-time download progress tracking.
- **Literature Snowballing** — Fetch and navigate through a paper's references (backward snowballing) and citations (forward snowballing) to discover related literature across generations via the OpenAlex API.
- **Parallel Metadata Retrieval** — Concurrent goroutine pipeline that queries Crossref, Unpaywall, OpenAlex, and Semantic Scholar simultaneously, merging the best metadata from each source.
- **Multi-Source PDF Downloads** — Resolves open-access PDF URLs from metadata providers, with an optional institutional EZProxy fallback channel for paywalled content your university has licensed.
- **Selective & Batch Downloading** — Use grid checkboxes to select specific papers for batch download (with configurable concurrency), or download individual PDFs from the preview panel.
- **Broad File Import** — Extracts DOIs from BibTeX (`.bib`), RIS (`.ris`), EndNote XML (`.xml`), Zotero JSON (`.json`), and plain text (`.txt`, `.csv`) files with automatic format detection.
- **Citation Export** — Generate formatted citations in APA 7th, MLA, Chicago, Harvard, IEEE, and Vancouver styles, or export as BibTeX / RIS. Export the entire workspace as a single BibTeX file.
- **Standalone Binary** — Compiles to a single-file executable (~15 MB) with no external runtime dependencies.

---

## 🚀 Installation & Building

### Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| **Go** | 1.26+ | `go version` |
| **Node.js** | 18+ | `node -v` |
| **npm** | 9+ | `npm -v` |
| **Wails CLI** | v2 | `wails version` |

Install the Wails CLI if you don't have it:

```bash
go install github.com/wailsapp/wails/v2/cmd/wails@latest
```

### Clone & Build

```bash
git clone https://github.com/dmcalungsod/LitNexus.git
cd LitNexus
wails build
```

The compiled executable will be output to `build/bin/LitNexus.exe`.

### Development Mode

For hot-reloading during development:

```bash
wails dev
```

This starts the Go backend and Vite dev server simultaneously with live-reload for frontend changes.

---

## 💻 Usage

### Running

Launch the built executable directly:

```bash
.\build\bin\LitNexus.exe
```

Or use development mode (`wails dev`) for a live-reloading environment.

### Step-by-Step Workflow

1. **Configure (⚙ Settings):** Click the settings icon to enter your institutional email address (used for Unpaywall / Crossref APIs), optionally configure an EZProxy gateway prefix, and set your PDF output directory.
2. **Add a Seed Paper:** Click **"＋ Add DOI"** in the root workspace to manually add a starting paper by DOI. Metadata is resolved automatically from multiple sources in parallel.
3. **Import Citation Files:** Use **"Import File"** to bulk-import DOIs from `.bib`, `.ris`, `.xml`, `.json`, `.txt`, or `.csv` files.
4. **Explore via Snowballing:** Select a paper and use the preview panel to **"Fetch"** its references (backward) or citations (forward) to discover related literature across generations.
5. **Navigate Generations:** Use breadcrumb navigation to traverse the discovery tree. Click **"View"** to see discovered papers in the grid, and **"‹ Back"** to return to the parent.
6. **Filter & Select:** Use the search bar and status/generation filters to organize the grid view. Use checkboxes to select papers for batch operations.
7. **Download PDFs:** Click **"↓ Download Selected"** for batch downloads with real-time progress, or use the **"↓ Download PDF"** button on any individual paper's preview panel.
8. **Read & Cite:** Click **"Open PDF"** from the preview panel to open downloaded files. Use the citation tools to generate formatted references in your preferred style.

---

## 🏗️ Architecture

LitNexus is a [Wails v2](https://wails.io/) application with a Go backend and a React/TypeScript frontend.

```
                    ┌─────────────────────────────────────────┐
                    │           Wails v2 Runtime              │
                    │  (WebView2 on Windows, WebKit on macOS) │
                    └─────────┬───────────────┬───────────────┘
                              │               │
                    ┌─────────▼───────┐ ┌─────▼───────────────┐
                    │   Go Backend    │ │  React Frontend     │
                    │                 │ │  (TypeScript + TSX) │
                    │  ┌────────────┐ │ │  ┌────────────────┐ │
                    │  │ app.go     │◄├─┤─►│ App.tsx        │ │
                    │  │ (Wails    │ │ │  │ (Single-page   │ │
                    │  │  bindings)│ │ │  │  application)  │ │
                    │  └─────┬─────┘ │ │  └────────────────┘ │
                    │        │       │ │  Tailwind CSS        │
                    │  ┌─────▼─────┐ │ │  Lucide Icons        │
                    │  │ internal/ │ │ │  Vite Build          │
                    │  └───────────┘ │ └──────────────────────┘
                    └────────────────┘
```

### Go Backend (`internal/`)

| Package | Description |
|---------|-------------|
| `config` | API endpoint URLs and constants (Crossref, Unpaywall, OpenAlex, Semantic Scholar, arXiv, PubMed, DOAJ, Zenodo, OSF, CORE). |
| `database` | SQLite workspace persistence via `modernc.org/sqlite` (pure-Go, no CGO). Stores papers, citation edges, discovery provenance, and sessions. |
| `domain` | Core data models — `Paper`, `Edge`, `PaperDiscovery`, `DownloadResult`, `Metadata`. |
| `downloader` | PDF download engine with parallel metadata resolution, file validation (PDF header + size checks), APA-style filename generation, and institutional proxy fallback. |
| `metadata` | Pluggable `Source` interface with four concurrent implementations (Crossref, Unpaywall, OpenAlex, Semantic Scholar). The `Fetcher` merges results with enrichment and early-return on high-confidence sources. |
| `parsers` | DOI extraction from BibTeX, RIS, EndNote XML, Zotero JSON, and plain text with format auto-detection. |
| `settings` | JSON-based application settings persistence (`~/.litnexus/settings.json`). |
| `snowball` | Literature snowballing engine using the OpenAlex API — resolves referenced works (backward) and citing works (forward) in batches of 50. |
| `utils` | DOI cleaning/validation, safe filename generation, APA author formatting, multi-style citation generation (APA, MLA, Chicago, Harvard, IEEE, Vancouver, BibTeX, RIS). |

### Frontend (`frontend/`)

| Technology | Role |
|-----------|------|
| **React 18** | UI framework |
| **TypeScript** | Type-safe component logic |
| **Tailwind CSS 3** | Utility-first styling |
| **Vite** | Build tooling and dev server |
| **Lucide React** | Icon library |
| **Wails JS Runtime** | Go ↔ JS bridge and event system |

---

## 📂 Project Structure

```text
LitNexus/
│
├── main.go                        # Wails application entry point
├── app.go                         # App struct — exposes Go methods to frontend via Wails bindings
│
├── internal/
│   ├── config/
│   │   └── config.go              # API endpoint URLs and constants
│   ├── database/
│   │   └── db.go                  # SQLite database manager (papers, edges, discoveries, sessions)
│   ├── domain/
│   │   └── paper.go               # Core data models (Paper, Edge, Metadata, DownloadResult)
│   ├── downloader/
│   │   └── downloader.go          # PDF download engine with proxy fallback and file validation
│   ├── metadata/
│   │   ├── source.go              # Source interface and shared HTTP client
│   │   ├── fetcher.go             # Parallel metadata fetcher with enrichment
│   │   ├── crossref.go            # Crossref API source
│   │   ├── unpaywall.go           # Unpaywall API source
│   │   ├── openalex.go            # OpenAlex API source
│   │   └── semanticscholar.go     # Semantic Scholar API source
│   ├── parsers/
│   │   └── parsers.go             # DOI extraction from citation files (.bib, .ris, .xml, .json, .txt, .csv)
│   ├── settings/
│   │   └── settings.go            # Settings manager with JSON persistence (~/.litnexus/)
│   ├── snowball/
│   │   └── engine.go              # Literature snowballing engine (references + citations via OpenAlex)
│   └── utils/
│       ├── utils.go               # DOI cleaning, safe filenames, citation formatting
│       └── utils_test.go          # Unit tests for utility functions
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx               # React entry point
│   │   ├── App.tsx                # Main single-page application component
│   │   └── index.css              # Global styles
│   ├── index.html                 # HTML shell
│   ├── package.json               # npm dependencies (React, Lucide, Tailwind CSS, Vite)
│   ├── tsconfig.json              # TypeScript configuration
│   ├── vite.config.ts             # Vite build configuration
│   ├── tailwind.config.js         # Tailwind CSS configuration
│   ├── postcss.config.js          # PostCSS configuration
│   └── wailsjs/                   # Auto-generated Wails JS/TS bindings
│
├── assets/
│   └── favicon.ico                # Application icon
│
├── build/                         # (GitIgnored) Compiled executables
├── logs/                          # (GitIgnored) Application logs
│
├── go.mod                         # Go module definition
├── go.sum                         # Go dependency checksums
├── wails.json                     # Wails project configuration
├── config.ini                     # Runtime mode configuration
├── version_info.txt               # Windows executable version metadata
│
├── .pre-commit-config.yaml        # Pre-commit hooks (Ruff, mypy — legacy)
├── .gitignore
├── LICENSE.txt                    # MIT License
└── README.md                      # This file
```

---

## ⚠️ Security, Limitations & Legal Notice

### Security

- **Antivirus:** This application downloads `.pdf` files from the internet to your disk. While the tool only accesses public academic repositories, all users should run active antivirus software with real-time scanning enabled.
- **PDF Validation:** Downloaded files are validated against both a minimum file size threshold (5 KB) and the PDF binary header (`%PDF-`) before being written to disk.
- **SSL Verification:** All HTTP connections use standard TLS/SSL verification.

### Limitations

- **Open Access Only:** This tool **cannot** bypass paywalls. It only searches for legally-hosted, open-access versions of articles. If a PDF is not available from any OA source, the download for that DOI will fail. An optional institutional EZProxy gateway can be configured for content your institution has licensed.
- **API Rate Limits:** The tool is designed to be a polite client, but APIs like Unpaywall and Crossref have rate limits. Processing large batches of DOIs may result in temporary throttling.
- **Metadata Quality:** Filenames follow the pattern `Author et al., Year - Title - DOI.pdf` and depend entirely on the metadata returned by upstream APIs. Incomplete metadata will produce partial filenames.
- **Snowballing Depth:** The snowballing engine currently fetches up to 50 papers per batch from OpenAlex.

### Legal, Terms of Service, and Acknowledgments

This tool is an API client. As a user, you are responsible for abiding by the terms of service for all APIs this tool contacts. This tool is provided "as is," without warranty, and the authors are not liable for any misuse.

**User Responsibilities & Content Notice:**
- **Intended Use:** This Software is intended solely for the purpose of accessing and downloading open-access content.
- **Compliance:** You, the user, are solely responsible for your use of this Software. You must ensure that your actions comply with all applicable copyright laws, institutional policies, and the terms of service of any third-party APIs used by this Software.
- **No Guarantee:** The Software provides no guarantee that the content it retrieves is, in fact, open-access. The Author is not responsible for any content downloaded by the user in violation of any laws or agreements.

### Open Data Services

This project gratefully acknowledges the following open data services:

- **[Crossref](https://www.crossref.org/services/metadata-retrieval/)** — Scholarly metadata and DOI registration.
- **[Unpaywall](https://unpaywall.org/products/api)** — Open-access article discovery.
- **[OpenAlex](https://openalex.org/)** — Open scholarly metadata index.
  > Priem, J., Piwowar, H., & Orr, R. (2022). *OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts.* arXiv. [https://arxiv.org/abs/2205.01833](https://arxiv.org/abs/2205.01833)
- **[Semantic Scholar](https://www.semanticscholar.org/product/api)** — AI-powered research discovery.

---

## ✨ Attributions

The application icon (`favicon.ico`) was downloaded from [Magnific](https://magnific.com/) stock images.

---

## 📜 License

This entire project — both its source code and the distributed executable — is licensed under the **MIT License**. See the [LICENSE.txt](LICENSE.txt) file for details.
