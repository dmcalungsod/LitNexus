# LitNexus Application Summary

This document provides a detailed, step-by-step summary of how the LitNexus application functions and how users can interact with it to build literature graphs and download academic papers.

## Application Overview

LitNexus is a PySide6-based graphical user interface (GUI) application designed to serve as a "Literature Workspace." Its primary functions are:
1. Acting as a starting point (Seed) for academic research.
2. Building out a literature graph by discovering references (past papers) and citations (future papers).
3. Selectively downloading Open-Access (OA) PDF versions of those papers.
4. Persisting all data, lineage, and file paths locally in an SQLite database (`workspace.db`).

---

## Step-by-Step User Interaction Guide

### 1. Launching and Configuration
- **Start the App:** The user launches the application by running `python run.py`.
- **Initial Setup (Crucial):** Before downloading, the user should click the **⚙ Settings** button in the top-right overlay. They must configure their email address for the Unpaywall API, set their desired output directory for PDFs, and adjust parallel download limits.

### 2. Seeding the Workspace
- **Add a Paper:** In the "Root" view (Generation 0), the user clicks the green **"＋ Add DOI"** button at the bottom left.
- **Input DOI:** The user pastes a Digital Object Identifier (e.g., `10.1038/s41586-020-2649-2`).
- **Metadata Resolution:** The app automatically spawns a background thread (`core.py` -> `metadata_fetcher.py`) to query multiple APIs (Crossref, OpenAlex, Semantic Scholar, etc.). Once resolved, the paper's Title, Authors, and Year appear in the main data grid.

### 3. Exploring the Literature Network (Snowballing)
- **Select a Paper:** The user clicks on the newly added paper in the grid.
- **Preview Panel:** The right-side panel populates with the abstract and network statistics.
- **Fetch Lineage:**
  - **Past (References):** The user clicks **"Fetch"** under the "References" box to find papers that this seed paper cited.
  - **Future (Citations):** The user clicks **"Fetch"** under the "Cited by" box to find papers that cite this seed paper.
- **Graph Expansion:** The background worker pulls these DOIs. Once complete, the button changes to **"View"**.
- **Navigate the Graph:** Clicking **"View"** changes the main grid to show Generation 1 papers. The user can continue this process recursively (Gen 2, Gen 3...). The breadcrumb navigation at the top (and the **"< Back"** button) allows the user to traverse back up the graph.

### 4. Searching and Filtering
- **Find Papers:** The user can use the search bar above the grid to instantly filter papers by Title, Authors, or DOI.
- **Status/Generation:** Dropdowns allow the user to view only "Pending" downloads, or only "Seed" papers, keeping the workspace organized as it grows.

### 5. Selectively Downloading PDFs
- **Select Papers:** The user checks the boxes in the leftmost `✓` column of the grid for the specific papers they wish to read. They can also use the **"Select All"** button.
- **Trigger Bulk Download:** The user clicks **"↓ Download Selected"**. 
- **Direct Download:** Alternatively, when viewing a paper's details in the right-side preview, the user can click the large blue **"↓ Download PDF"** button to queue just that one paper.
- **Download Pipeline:** The app routes the selected DOIs to the `DownloadManager`, which uses multi-threading to attempt downloads across prioritized OA sources (Unpaywall -> PMC -> OpenAlex, etc.).
- **Progress:** A progress bar appears at the bottom, and real-time logs can be viewed by clicking the **"Activity"** overlay button at the top right.

### 6. Reading the PDFs
- **Success:** Once a PDF is downloaded, its status in the grid updates to `✓ Ready`. The local file path is saved in the SQLite database.
- **Open PDF:** The user selects the downloaded paper in the grid. The hero button in the preview panel turns green and reads **"Open PDF"**.
- **View:** Clicking it uses the operating system's native launcher to open the PDF directly, avoiding any manual file browsing.

---

## Technical Architecture Summary

- **UI Framework:** PySide6 (Widgets: `main_window.py`, `workspace_widget.py`, `paper_preview_widget.py`).
- **Database:** SQLite (`database.py`) tracks papers, metadata, PDF status, generation depth, and directional edges (discoveries).
- **Network & Concurrency:** Multi-threaded download and metadata fetching pipelines to prevent UI blocking (`download_manager.py`, `core.py`).
- **APIs:** Fallback pipeline querying 10+ open-access data sources.
