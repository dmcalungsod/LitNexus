# Open-Access PDF Retrieval System

![Last Commit](https://img.shields.io/github/last-commit/Zosick/LitNexus?style=flat-square)
![Forks](https://img.shields.io/github/forks/Zosick/LitNexus?style=flat-square)
![Issues](https://img.shields.io/github/issues/Zosick/LitNexus?style=flat-square)
![Contributors](https://img.shields.io/github/contributors/Zosick/LitNexus?style=flat-square)
![Stars](https://img.shields.io/github/stars/Zosick/LitNexus?style=flat-square)
![License](https://img.shields.io/github/license/Zosick/LitNexus?style=flat-square)

A modern graphical user interface (GUI) application designed to efficiently download open-access PDF articles using their Digital Object Identifiers (DOIs). The system features a robust, multi-source retrieval pipeline and supports a wide range of academic citation file formats.

> [!NOTE]
> **Migration to PySide6**: This project has completely transitioned from a command-line interface to a robust PySide6 GUI workspace.

> [!WARNING]
> **Development Status**: This application is currently under active development and is not yet production-ready. The system's behavior may be unstable or incomplete, and users may encounter unexpected errors, unhandled exceptions, and numerous known or potentially unknown bugs during operation.

## ✨ Key Features

- **Modern GUI Workspace:** A sleek, dark-mode PySide6 interface featuring a split-pane design (data grid + preview panel) that acts as your central literature hub.
- **Literature Snowballing:** Instantly fetch and navigate through references (past papers) and citations (future papers) to discover new literature.
- **Selective Downloading:** Use the grid's checkboxes to selectively download specific PDFs, or trigger one-off downloads directly from the preview panel.
- **Broad File Support:** Extracts DOIs directly from various citation formats, including:
  - BibTeX (`.bib`)
  - RIS (`.ris`)
  - EndNote XML (`.xml`, `.enw`)
  - Zotero JSON (`.json`)
  - Plain text lists (`.txt`, `.csv`)
- **Advanced Metadata Pipeline:** Intelligently fetches and combines article metadata (Title, Author, Year) from a prioritized list of **10 sources**:
  - Crossref
  - Unpaywall
  - CORE
  - PubMed Central (PMC)
  - Directory of Open Access Journals (DOAJ)
  - Zenodo
  - Open Science Framework (OSF)
  - arXiv
  - OpenAlex
  - Semantic Scholar
- **Parallel Metadata Fetching:** Concurrently queries multiple metadata sources to find the best available metadata and PDF links faster.
- **Smart Download Pipeline:** If metadata is found, it attempts to download the PDF from a separate, prioritized pipeline of OA sources.
- **Parallel Downloads:** Utilizes multi-threading to download multiple PDFs simultaneously, significantly speeding up the process.
- **Standardized Naming:** Automatically generates clean, APA 7th-style filenames:
  `Author et al., Year - Title - DOI.pdf`
- **Standalone Executable:** Comes with a professional build script (`build_exe.py`) to compile the entire application into a single, distributable `.exe` file for Windows, complete with an icon, version info, and optional code signing.

---

## 🚀 Installation

To get started, clone the repository and install the required Python packages.

1. **Clone the repository:**

    ```bash
    git clone https://github.com/Zosick/LitNexus.git
    cd LitNexus
    ```

2. **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    ```

    Activate it:

    - On Windows: `.\venv\Scripts\activate`
    - On macOS/Linux: `source venv/bin/activate`

3. **Install dependencies:**
    A `requirements.txt` file is included.

    ```bash
    pip install -r requirements.txt
    ```

    _(The file includes: `rich`, `requests`, `bibtexparser`, `rispy`, `beautifulsoup4`, `defusedxml`)_

---

## 💻 Usage

Run the GUI application from the project's root directory:

```bash
python -m src.downloader.gui
```

Or use the standalone executable (after building):

```bash
.\dist\"LitNexus.exe"
```

### Step-by-Step Workflow

1. **Configure (⚙ Settings):** Start by entering your email address for Unpaywall and selecting your output directory.
2. **Add a Seed Paper:** Click **"＋ Add DOI"** in the root workspace to manually add a starting paper. The app will resolve its metadata instantly.
3. **Explore the Graph:** Select the paper and look at the right-side preview panel. Click **"Fetch"** under References or Citations to discover related literature.
4. **Navigate:** Click **"View"** to see the newly discovered Generation 1 papers in the grid. Use the breadcrumbs (`< Back`) to traverse up and down your discovery tree.
5. **Filter & Select:** Use the search bar and generation/status filters to organize the view. Use the checkboxes (`✓`) to select the papers you want to read.
6. **Download PDFs:** Click **"↓ Download Selected"** to fetch the OA PDFs in the background. Or, click the large **"↓ Download PDF"** hero button on any single paper's preview.
7. **Read:** Once downloaded, click **"Open PDF"** from the preview panel to view it instantly.

---

## 📦 Building the Executable

You can compile the entire project into a single `.exe` file using the included build script.

1. **Install PyInstaller:**

    ```bash
    pip install pyinstaller
    ```

2. **Run the build script:**

    ```bash
    python build_exe.py
    ```

The script will automatically clean previous artifacts, build the executable, and place the final `LitNexus.exe` file inside the `dist` folder.

### Code Signing (Optional)

The build script includes a feature to digitally sign the executable. To use it:

- Place your `.pfx` code signing certificate anywhere in the project directory.
- The script will automatically find it and prompt you for the password during the build process.

---

## ⚠️ Security, Limitations & Legal Notice

### Security

- **Antivirus:** This application writes `.pdf` files from the internet to your disk. While the tool only downloads from public academic repositories, all users should run active antivirus software (e.g., Windows Defender) that provides real-time scanning of all new files.
- **SSL Verification:** By default, this tool verifies SSL certificates. You can disable this in the settings (option `Bypass SSL verification?`), but it is **not recommended** as it makes you vulnerable to man-in-the-middle (MITM) attacks. Only use this if you are behind a corporate firewall that uses self-signed certificates.

### Limitations

- **Open Access Only:** This tool is **NOT** a "piracy" tool and **cannot** bypass paywalls. It _only_ searches for legally-hosted, open-access (OA) versions of articles. If a PDF is not available from one of the 10+ OA sources, the download for that DOI will fail.
- **API Rate Limits:** The tool is designed to be a "polite" client, but some APIs (like Unpaywall and Crossref) have rate limits. If you are processing thousands of DOIs, you may be temporarily rate-limited.
- **Metadata Quality:** The filename `Author et al., Year - Title - DOI.pdf` is 100% dependent on the metadata returned by the APIs. If an API provides incomplete data, the filename will reflect that (e.g., `Unknown Author, 2024 - Title - DOI.pdf`).

### Legal, Terms of Service, and Acknowledgments

This tool is an API client. As a user, you are responsible for abiding by the terms of service for all APIs this tool contacts. This tool is provided "as is," without warranty, and the authors are not liable for any misuse.

This project gratefully acknowledges the following open data services:

- **Crossref:** [https://www.crossref.org/services/metadata-retrieval/](https://www.crossref.org/services/metadata-retrieval/)
- **Unpaywall:** [https://unpaywall.org/products/api](https://unpaywall.org/products/api)
- **OpenAlex:** Please cite their paper:
  > Priem, J., Piwowar, H., & Orr, R. (2022). _OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts._ arXiv. [https://arxiv.org/abs/2205.01833](https://arxiv.org/abs/2205.01833)
- **CORE:** Please cite their paper:
  > Knoth, P. and Zdrahal, Z. (2012) _CORE: Three Access Levels to Underpin Open Access._ D-Lib Magazine, 18(11/12). [http://www.dlib.org/dlib/november12/knoth/11knoth.html](http://www.dlib.org/dlib/november12/knoth/11knoth.html)
- **Semantic Scholar:** This tool uses the Semantic Scholar API in accordance with its license. [https://www.semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)
- **arXiv:** [https://arxiv.org/](https://arxiv.org/)
- **PubMed Central (PMC):** [https://www.ncbi.nlm.nih.gov/pmc/](https://www.ncbi.nlm.nih.gov/pmc/)
- **Directory of Open Access Journals (DOAJ):** [https://doaj.org/](https://doaj.org/)
- **Zenodo:** [https://zenodo.org/](https://zenodo.org/)
- **Open Science Framework (OSF):** [https://osf.io/](https://osf.io/)

---

## 📂 Project Structure

This project has been refactored for clarity and maintainability.

```text
LitNexus/
│
├── src/
│   └── downloader/
│       ├── __init__.py
│       ├── config.py              # API endpoints and constants
│       ├── core.py                # The main Downloader orchestration class
│       ├── download_executor.py   # Executes individual file downloads
│       ├── download_manager.py    # Threaded download manager
│       ├── download_pipeline.py   # Multi-source download pipeline
│       ├── exceptions.py
│       ├── filename_generator.py  # APA-style filename builder
│       ├── metadata_fetcher.py    # Parallel metadata retrieval
│       ├── parsers.py             # DOI extraction from .bib, .ris, etc.
│       ├── protocol.py            # Protocol definitions
│       ├── settings.py            # Settings models
│       ├── settings_manager.py    # Settings persistence
│       ├── source_manager.py      # Manages source prioritization
│       ├── sources/               # Metadata and download sources
│       │   ├── __init__.py
│       │   ├── base.py            # Abstract Base Source class
│       │   ├── arxiv_source.py
│       │   ├── core_api_source.py
│       │   ├── crossref_source.py
│       │   ├── doaj_source.py
│       │   ├── doi_resolver_source.py
│       │   ├── openalex_source.py
│       │   ├── osf_source.py
│       │   ├── pmc_source.py
│       │   ├── semantic_scholar_source.py
│       │   ├── unpaywall_source.py
│       │   └── zenodo_source.py
│       ├── gui/                   # PySide6 GUI package
│       │   ├── __init__.py
│       │   ├── __main__.py             # Makes the GUI runnable
│       │   ├── main_window.py          # Main application layout and controller
│       │   ├── workspace_widget.py     # Data grid and central workspace UI
│       │   ├── paper_preview_widget.py # Right-side paper details and actions
│       │   ├── paper_details_dialog.py # Pop-up dialog for extended paper info
│       │   ├── settings_widget.py      # App configuration panel
│       │   └── status_widget.py        # Progress, logs, and activity overlay
│       ├── types.py               # Type definitions
│       └── utils.py               # Filename sanitizers and author formatters
│
├── tests/
│   ├── conftest.py
│   ├── test_core.py
│   ├── test_download_manager.py
│   ├── test_gui.py
│   └── test_parsers.py
│
├── assets/
│   └── favicon.ico
│
├── data/                          # (GitIgnored) Saved settings
├── downloads/                     # (GitIgnored) Default PDF output folder
├── output/                        # (GitIgnored) Failed DOI lists
│
├── run.py                         # Simple entry script
├── build_exe.py                   # PyInstaller build script
├── requirements.txt
├── pyproject.toml                 # Ruff and mypy configuration
├── .pre-commit-config.yaml
│
├── README.md                      # This file
├── LICENSE.txt                    # MIT License for the source code
├── EULA.txt                       # End-User License Agreement for the executable
│
└── .gitignore
```

## ✨ Attributions

The application icon (`favicon.ico`) was downloaded from [Magnific](https://magnific.com/) stock images.

---

## 📜 License & EULA

This project's source code is licensed under the **MIT License**. See the `LICENSE.txt` file for details.

The distributed executable (`LitNexus.exe`) is governed by the **End-User License Agreement**. See the `EULA.txt` file for details on your rights and responsibilities when _using_ the software.
