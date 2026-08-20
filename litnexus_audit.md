# LitNexus — Full Application Audit

## What Is LitNexus?

LitNexus is a **desktop academic literature management tool** built as a [Wails v2](https://wails.io/) application (Go backend + React/TypeScript frontend). It helps researchers:

1. **Discover** — Add papers by DOI, then "snowball" outward to find references (backward) and citations (forward) via the OpenAlex API.
2. **Download** — Fetch open-access PDFs from Unpaywall, Crossref, OpenAlex, and Semantic Scholar, with optional institutional proxy fallback.
3. **Organize** — View papers in a data grid with search, filter, sort, breadcrumb navigation across citation generations, and multi-select.
4. **Cite & Export** — Generate formatted citations in APA, MLA, Chicago, Harvard, IEEE, Vancouver, BibTeX, and RIS. Export the full workspace as a single BibTeX file.

It compiles to a single ~15 MB executable with no external runtime dependencies.

---

## Architecture Summary

```
┌────────────────────────────────────────────────────────────┐
│                     Wails v2 Runtime                        │
│              (WebView2 on Windows, WebKit on macOS)         │
├─────────────────────────┬──────────────────────────────────┤
│     Go Backend          │      React Frontend              │
│                         │                                  │
│  app.go (Wails binds)   │  App.tsx (1661-line SPA)         │
│  internal/              │  index.css (theme vars)          │
│   ├─ config/            │  Tailwind CSS 3                  │
│   ├─ database/ (SQLite) │  Lucide React icons              │
│   ├─ domain/            │  Vite build                      │
│   ├─ downloader/        │                                  │
│   ├─ metadata/          │  Wails JS/TS bindings            │
│   │   ├─ Crossref       │  (auto-generated)                │
│   │   ├─ Unpaywall      │                                  │
│   │   ├─ OpenAlex       │                                  │
│   │   └─ Semantic Scholar│                                 │
│   ├─ parsers/           │                                  │
│   ├─ settings/          │                                  │
│   ├─ snowball/          │                                  │
│   └─ utils/             │                                  │
└─────────────────────────┴──────────────────────────────────┘
```

| Layer | Tech | Details |
|-------|------|---------|
| Desktop Shell | Wails v2.14.0 | WebView2-backed desktop wrapper |
| Backend | Go 1.26.5 | Single-threaded SQLite, concurrent metadata fetching, PDF download engine |
| Frontend | React 18 + TypeScript + Tailwind CSS 3 + Vite | Single monolithic `App.tsx` component |
| Database | `modernc.org/sqlite` (pure-Go, no CGO) | Tables: `papers`, `edges`, `paper_discoveries`, `sessions` |
| Settings | JSON file at `~/.litnexus/settings.json` | Email, proxy, output dir, SSL, UI mode |

---

## What's Fully Implemented (Working)

### Backend (Go)

| Feature | File(s) | Status |
|---------|---------|--------|
| DOI validation & cleaning | [utils.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/utils/utils.go) | ✅ |
| Parallel metadata fetching (4 sources) | [fetcher.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/metadata/fetcher.go), [crossref.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/metadata/crossref.go), [unpaywall.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/metadata/unpaywall.go), [openalex.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/metadata/openalex.go), [semanticscholar.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/metadata/semanticscholar.go) | ✅ |
| PDF download (single + batch, concurrent) | [downloader.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/downloader/downloader.go) | ✅ |
| PDF validation (header + size) | [downloader.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/downloader/downloader.go#L178-L197) | ✅ |
| Institutional proxy fallback | [downloader.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/downloader/downloader.go#L118-L137) | ✅ |
| Literature snowballing (OpenAlex) | [engine.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/snowball/engine.go) | ✅ |
| Citation file parsing (.bib, .ris, .xml, .json, .txt, .csv) | [parsers.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/parsers/parsers.go) | ✅ |
| SQLite persistence (papers, edges, discoveries, sessions) | [db.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/database/db.go) | ✅ |
| Settings persistence (JSON) | [settings.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/settings/settings.go) | ✅ |
| Multi-style citation generation (8 styles) | [utils.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/utils/utils.go#L93-L130) | ✅ |
| Clipboard read/write | [app.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/app.go#L229-L237) | ✅ |
| Open PDF in OS viewer | [app.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/app.go#L190-L227) | ✅ |
| Workspace clear | [app.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/app.go#L272-L275) | ✅ |
| Unit tests (utils) | [utils_test.go](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/utils/utils_test.go) | ✅ |

### Frontend (React/TSX)

| Feature | Location in [App.tsx](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/frontend/src/App.tsx) | Status |
|---------|------|--------|
| Typed toast system (success/error/warning/info) | L42–46, L139–145, L701–706, L721–737 | ✅ |
| Loading cursor during async ops | L170–178 | ✅ |
| 4-theme switcher (dark/light/midnight/warm) | L61–66, L95–97, L163–166, L841–860 | ✅ |
| Theme CSS variables | [index.css](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/frontend/src/index.css#L63-L135) | ✅ |
| First-launch onboarding modal | L118, L182–187, L1603–1657 | ✅ |
| Help button (re-open onboarding) | L876–883 | ✅ |
| Auto clipboard DOI detection | L196–216, L739–764 | ✅ |
| Data grid (sortable, filterable, searchable) | L997–1147 | ✅ |
| Breadcrumb navigation stack | L120–123, L398–414, L903–944 | ✅ |
| Preview panel (metadata, DOI, download, cite) | L1151–1402 | ✅ |
| Citation generator (8 styles, copy-to-clipboard) | L1253–1312 | ✅ |
| Snowball controls (refs + cites) | L1314–1386 | ✅ |
| Failed download detail tooltip (grid) | L1104–1112 | ✅ |
| Failed download error banner (preview) | L1181–1211 | ✅ |
| Retry button (grid + preview) | L1121–1128, L1194–1199 | ✅ |
| Batch download progress bar | L1406–1434 | ✅ |
| Batch failure summary modal | L1436–1484 | ✅ |
| Activity log panel | L1486–1536 | ✅ |
| Settings modal | L1538–1601 | ✅ |
| Real-time download events (Wails EventsOn) | L220–275 | ✅ |

---

## What's Missing or Incomplete

### 🔴 Critical / Functional Gaps

| # | Gap | Details | Affected Files | Status |
|---|-----|---------|----------------|--------|
| 1 | **File Import UI is missing** | The backend exposes `ImportFile(path)` and parsers extract DOIs from `.bib`, `.ris`, `.xml`, `.json`, `.txt`, `.csv` files. | `app.go`, `App.tsx` | ✅ **Fixed**: Added `SelectAndImportFile()` with OS native file dialog (`runtime.OpenFileDialog`) and header "Import File" button. |
| 2 | **Crossref doesn't extract abstracts** | Crossref provides abstracts via `message.abstract`. | `crossref.go` | ✅ **Fixed**: Added `Abstract` field parsing and JATS XML tag stripping in `crossref.go`. |
| 3 | **Crossref doesn't extract PDF URLs** | Crossref provides `message.link[].URL` with content-type `application/pdf`. | `crossref.go` | ✅ **Fixed**: Added `Link` array parsing for `application/pdf` URLs in `crossref.go`. |
| 4 | **No `verify_ssl` implementation** | `AppSettings.VerifySSL` existed but was not wired to HTTP client TLS configurations. | `source.go`, `downloader.go`, `engine.go`, `app.go` | ✅ **Fixed**: Wired `TLSClientConfig` with `InsecureSkipVerify: !verifySSL` across all metadata, downloader, and snowball clients. |
| 5 | **`Unpaywall email` not refreshed on save** | When `SaveSettings` is called ([app.go L283](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/app.go#L283)), Unpaywall email was not refreshed. | `app.go` | ✅ **Fixed**: Recreates `Fetcher` and `SnowballEngine` instances with updated email on `SaveSettings`. |
| 6 | **Database not closed on shutdown** | `database.Manager.Close()` exists ([db.go L38](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/internal/database/db.go#L38)) but was never called. | `app.go`, `main.go` | ✅ **Fixed**: Added `shutdown(ctx)` method to `App` and wired `OnShutdown: app.shutdown` in `main.go`. |

### 🟡 Moderate Issues

| # | Issue | Details | Status |
|---|-------|---------|--------|
| 7 | **Single `window.confirm()` remains** | `handleClearWorkspace` used browser native `window.confirm()`. | ✅ **Fixed**: Replaced browser native dialog with a custom themed dark-mode modal. |
| 8 | **`config.ini` is dead code** | Configured `ui_mode = research` but unused by code. | ✅ **Fixed**: Removed dead `config.ini` file from project root. |
| 9 | **`sessions` table unused** | Created in schema but unused. | ⏳ Pending |
| 10 | **`external_*` / `*_fetch_status` columns populated but not displayed** | The `Paper` model includes `ExternalReferenceCount` and `ExternalCitationCount` fields, but frontend never displayed them. | ✅ **Fixed**: Updated `Paper` interface in `App.tsx` and exposed online/external reference and citation counts in the Preview Panel literature graph controls. |
| 11 | **Pre-commit hooks are for Python** | [.pre-commit-config.yaml](file:///d:/Downloads/Github%20Projects/LitNexus%20-%20Copy/.pre-commit-config.yaml) configured Python linters. | ✅ **Fixed**: Removed legacy `.pre-commit-config.yaml`. |
| 12 | **`.gitignore` had Python-specific entries** | Included Python/Replit noise entries. | ✅ **Fixed**: Cleaned `.gitignore` to focus on Go, Node, Wails, and binaries. |
| 13 | **`venv/` directory committed** | Python virtual environment directory existed in project root. | ✅ **Fixed**: Deleted `venv/` directory. |
| 14 | **Individual paper deletion missing** | Users could only clear workspace, not delete a single paper. | ✅ **Fixed**: Implemented `DeletePaper(doi)` in Go database & app layer, exposed Wails binding, and added Trash action buttons in Data Grid and Preview Panel. |
| 15 | **`index.html` body hardcodes dark theme styles** | `class="bg-slate-950 text-slate-100"` was baked into `<body>`, causing background flash on Light theme during initial load. | ✅ **Fixed**: Replaced hardcoded tailwind slate classes with CSS variables (`bg-[var(--bg-primary)] text-[var(--text-primary)]`). |
| 16 | **Favicon mismatch** | `index.html` referenced `/favicon.svg` which was missing. | ✅ **Fixed**: Copied `favicon.ico` to `frontend/public/favicon.ico` and updated `index.html` reference. |
| 17 | **`completed` counter is not atomic** | `var completed int32` was declared as `int32` but protected by mutex. | ⏳ Pending |
| 18 | **Snowball engine timeout was zero** | Formerly `20 * http.DefaultClient.Timeout` (= 0). | ✅ **Fixed**: Set explicit `30 * time.Second` HTTP client timeout. |
| 19 | **OpenPDFFile uses Windows-only `cmd /c start`** | Formerly used Windows-only command execution. | ✅ **Fixed**: Added `openFileOS` helper supporting Windows (`cmd /c start`), macOS (`open`), and Linux (`xdg-open`). |

### 🟢 Minor / Polish

| # | Item | Details | Status |
|---|------|---------|--------|
| 20 | **Monolithic frontend** | The entire UI is a single `App.tsx` file. | ⏳ Pending |
| 21 | **No frontend tests** | No Jest/Vitest tests exist for the React frontend. | ⏳ Pending |

## API Surface Parity (Backend vs Frontend)

| Backend Method | Wails Binding | Frontend Usage |
|----------------|---------------|----------------|
| `AddDOI` | ✅ | ✅ Used |
| `ImportFile` | ✅ | ✅ Used (via `SelectAndImportFile`) |
| `SelectAndImportFile` | ✅ | ✅ Used |
| `DeletePaper` | ✅ | ✅ Used (Data Grid & Preview Panel trash buttons) |
| `GetAllPapers` | ✅ | ✅ Used |
| `GetPastReferences` | ✅ | ✅ Used |
| `GetFutureCitations` | ✅ | ✅ Used |
| `FetchPastReferences` | ✅ | ✅ Used |
| `FetchFutureCitations` | ✅ | ✅ Used |
| `DownloadPDF` | ✅ | ✅ Used |
| `DownloadBatchPDFs` | ✅ | ✅ Used |
| `OpenPDFFile` | ✅ | ✅ Used |
| `CopyToClipboard` | ✅ | ✅ Used |
| `ReadClipboard` | ✅ | ✅ Used |
| `GenerateFormattedCitation` | ✅ | ✅ Used |
| `GenerateAPACitation` | ✅ | ❌ Not called (superseded by `GenerateFormattedCitation`) |
| `GenerateBibTeX` | ✅ | ✅ Used (fallback) |
| `GenerateRIS` | ✅ | ✅ Used (fallback) |
| `ExportWorkspaceBibTeX` | ✅ | ✅ Used |
| `ClearWorkspace` | ✅ | ✅ Used |
| `GetSettings` | ✅ | ✅ Used |
| `SaveSettings` | ✅ | ✅ Used |

---

## README Accuracy

| README Claim | Reality |
|-------------|---------|
| "Import citation files (.bib, .ris, .xml, .json, .txt, .csv)" | ✅ Accurate — Native OS file dialog import works |
| "Multiple theme options" | ✅ Accurate — 4 themes work |
| "Real-time download progress tracking" | ✅ Accurate |
| "Literature snowballing" | ✅ Accurate |
| "APA-style filename generation" | ✅ Accurate |
| "Optional institutional EZProxy fallback" | ✅ Accurate |
| "WebKit on macOS" | ✅ Accurate — Cross-platform PDF opener (`openFileOS`) works on macOS/Linux/Windows |
| Prerequisite: "Go 1.26+" | ✅ Accurate — `README.md` and `go.mod` both specify Go 1.26+ |

---

## Codebase Metrics

| Metric | Value |
|--------|-------|
| Total Go source files | 12 |
| Total Go lines (excl. tests) | ~1,065 |
| Total Go test files | 1 |
| Total Go test lines | 65 |
| Frontend TSX source files | 1 (App.tsx) |
| Frontend TSX lines | 1,858 |
| Frontend CSS lines | 136 |
| NPM dependencies (runtime) | 3 (React, React-DOM, Lucide) |
| Go dependencies (direct) | 2 (Wails, modernc SQLite) |
| Database tables | 4 (papers, edges, paper_discoveries, sessions) |
| Metadata sources | 4 (Crossref, Unpaywall, OpenAlex, Semantic Scholar) |
| Citation styles | 8 (APA, MLA, Chicago, Harvard, IEEE, Vancouver, BibTeX, RIS) |

---

## Prioritized Recommendations

### Must Fix (Bugs / Broken Functionality)

1. **Fix snowball HTTP timeout** — `20 * http.DefaultClient.Timeout` = 0 (no timeout). Set an explicit timeout like `30 * time.Second`.
2. **Add `OnShutdown` hook to close DB** — Add `OnShutdown: app.shutdown` to `wails.Run` options and call `a.db.Close()`.
3. **Refresh Unpaywall email on settings save** — Recreate the `Fetcher`, `Downloader`, and `SnowballEngine` with updated email when `SaveSettings` is called.

### Should Fix (Missing Features / UX)

4. **Add File Import UI** — Add a button in the header that opens a Wails native file dialog (`runtime.OpenFileDialog`) and calls `ImportFile`.
5. **Add individual paper delete** — Expose `DeletePaper(doi)` in backend and add a delete action in the grid/preview panel.
6. **Replace `window.confirm()` with custom modal** — The Clear Workspace confirmation dialog is the last use of a native browser dialog.
7. **Add Crossref abstract and PDF URL extraction** — Parse `message.abstract` and `message.link[]` from Crossref responses.

### Nice to Have (Polish)

8. **Extract App.tsx into components** — Split into Header, DataGrid, PreviewPanel, Modals, etc.
9. **Remove dead Python artifacts** — Delete `venv/`, clean `.pre-commit-config.yaml`, `.gitignore` Python entries.
10. **Fix favicon reference** — Either convert `favicon.ico` to SVG or change `index.html` to reference `.ico`.
11. **Show external reference/citation counts in UI** — The data is already fetched and stored.
12. **Cross-platform PDF opening** — Use `runtime.BrowserOpenURL` or detect OS for `open` (macOS) / `xdg-open` (Linux).
13. **Add more backend tests** — Database, downloader, parsers, snowball.

---

## Summary

LitNexus is a well-structured, functional academic literature hub with a solid Go backend and polished React frontend. The core workflow (Add DOI → Snowball → Download → Cite) works end-to-end.

Across recent implementation passes, **20 total audit items** have been fully addressed:
- ✅ **Individual Paper Deletion Added**: Implemented `DeletePaper(doi)` in Go database and application layer, exposed Wails JS bindings, and added Trash action buttons in Data Grid row actions and Preview Panel header.
- ✅ **Initial Load Theme Flash Fixed**: Replaced hardcoded Tailwind slate classes on `<body>` in `index.html` with CSS variables (`bg-[var(--bg-primary)] text-[var(--text-primary)]`).
- ✅ **External Reference & Citation Counts Rendered**: Exposed `external_reference_count` and `external_citation_count` in `App.tsx` paper model and rendered online citation totals in Preview Panel literature graph controls.
- ✅ **Dead `config.ini` File Removed**: Cleaned up legacy dead configuration file from project root.
- ✅ **README Prerequisite Synchronized**: Updated `README.md` to state Go minimum version requirement as `1.26+`, matching `go.mod`.
- ✅ **File Import UI Added**: Native OS file dialog (`runtime.OpenFileDialog`) for `.bib`, `.ris`, `.xml`, `.json`, `.csv`, `.txt` files with header action button.
- ✅ **Custom Confirmation Modal**: Replaced native browser `window.confirm()` with a themed dark-mode modal for clearing workspace.
- ✅ **`verify_ssl` Setting Wired**: Configured `TLSClientConfig` with `InsecureSkipVerify: !verifySSL` across all metadata, downloader, and snowball HTTP clients.
- ✅ **Crossref Metadata Enriched**: Added extraction of abstracts (with JATS tag stripping) and `application/pdf` URLs.
- ✅ **Unpaywall Email Refresh Fixed**: Recreated `Fetcher` and `SnowballEngine` instances upon settings save.
- ✅ **Database Shutdown Clean**: Added `OnShutdown` hook to close SQLite handle on application exit.
- ✅ **Snowball HTTP Timeout Fixed**: Replaced `20 * http.DefaultClient.Timeout` (= 0) with explicit 30s timeout.
- ✅ **RIS Multi-Author Spec Compliant**: Author strings are split into individual `AU  -` lines per RIS specification.
- ✅ **Favicon Fixed**: Copied `favicon.ico` to `frontend/public/favicon.ico` and corrected `index.html` link reference.
- ✅ **Python Artifacts Cleaned**: Deleted `venv/` directory, removed `.pre-commit-config.yaml`, and cleaned `.gitignore`.
- ✅ **Startup Log Loop Fixed**: Resolved React state dependency loop on initial load in `App.tsx`.
- ✅ **Actionable Download Error Diagnostics**: Enriched preview banner, data grid tooltips, and batch summary modal with **Why** & **💡 How to resolve** details and settings/retry action buttons.
- ✅ **Isolated Snowball Spinner State**: Directional spinner (`references` | `citations`) prevents dual button spinning.
- ✅ **Seed Paper Protection & Auto-Breadcrumbs**: `GetAllPapers` query anchors Generation 0 papers at top, and snowballing auto-pushes breadcrumbs.
- ✅ **Cross-Platform PDF Opening**: Implemented OS-aware helper (`openFileOS`) supporting Windows (`cmd /c start`), macOS (`open`), and Linux (`xdg-open`).


