from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QHeaderView, 
    QAbstractItemView, QLabel, QMessageBox, QInputDialog, QProgressBar,
    QLineEdit, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QSettings, QItemSelectionModel, QTimer
from src.downloader.database import DatabaseManager
from src.downloader.gui.paper_preview_widget import PaperPreviewWidget
from src.downloader.logging_config import get_logger

logger = get_logger(__name__)

class PaperFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.status_filter = "All"
        self.gen_filter = "All"
        
    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        
        # DOI, Title, Authors, Year, Status, Network
        doi = model._data[source_row][0].lower()
        title = model._data[source_row][1].lower()
        authors = model._data[source_row][2].lower()
        status = model._data[source_row][4]
        
        # Generation is hidden in this model, but we can fetch it if we stored it in the model._data.
        # We need to add generation to model._data!
        
        # Search Filter
        if self.search_text:
            if self.search_text not in title and self.search_text not in authors and self.search_text not in doi:
                return False
                
        # Status Filter
        if self.status_filter != "All":
            if self.status_filter == "PDF" and "✓" not in status:
                return False
            elif self.status_filter == "Pending" and "↻" not in status:
                return False
            elif self.status_filter == "Failed" and "!" not in status:
                return False
                
        # Generation Filter
        generation = model._data[source_row][6]
        if self.gen_filter != "All":
            if self.gen_filter == "Seed" and generation != 0:
                return False
            elif self.gen_filter == "Gen 1" and abs(generation) != 1:
                return False
            elif self.gen_filter == "Gen 2+" and abs(generation) < 2:
                return False
                
        return True


class PaperTableModel(QAbstractTableModel):
    def __init__(self, data, checked_dois=None):
        super().__init__()
        self._data = data
        self.headers = ["✓", "DOI", "Title", "Authors", "Year", "PDF", "Network"]
        self.checked_dois = checked_dois if checked_dois is not None else set()

    def data(self, index, role):
        if role == Qt.CheckStateRole and index.column() == 0:
            doi = self._data[index.row()][0]
            return Qt.Checked if doi in self.checked_dois else Qt.Unchecked
            
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return ""
            col_idx = index.column() - 1
            if col_idx < len(self._data[index.row()]):
                val = str(self._data[index.row()][col_idx])
                # Truncate DOI for visual display only
                if index.column() == 1 and len(val) > 22:
                    return val[:22] + "..."
                return val
            return ""
        return None

    def flags(self, index):
        default_flags = super().flags(index)
        if index.column() == 0:
            return default_flags | Qt.ItemIsUserCheckable
        return default_flags
        
    def setData(self, index, value, role):
        if role == Qt.CheckStateRole and index.column() == 0:
            doi = self._data[index.row()][0]
            if value == Qt.Checked.value or value == Qt.Checked:
                self.checked_dois.add(doi)
            else:
                self.checked_dois.discard(doi)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

class WorkspaceWidget(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.db = DatabaseManager()
        
        # Navigation State
        self.current_mode = "root"  # "root", "past", "future"
        self.current_doi = None
        self.current_title = None
        self.nav_stack = []  # List of dicts: {"mode": ..., "doi": ..., "title": ...}
        
        self.setup_ui()
        self.refresh_grid()
        
        settings = QSettings("PDFRetriever", "Workspace")
        if settings.value("main_splitter"):
            self.main_splitter.restoreState(settings.value("main_splitter"))

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header / Breadcrumb
        header_layout = QHBoxLayout()
        self.back_btn = QPushButton("< Back")
        self.back_btn.clicked.connect(self.navigate_back)
        self.back_btn.hide()
        
        # Summary Layout (Breadcrumb + Stats)
        summary_vbox = QVBoxLayout()
        self.breadcrumb_label = QLabel("Literature Workspace: Root")
        self.breadcrumb_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.summary_label = QLabel("0 Seed · 0 References · 0 PDFs · 0 Pending")
        self.summary_label.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        
        summary_vbox.addWidget(self.breadcrumb_label)
        summary_vbox.addWidget(self.summary_label)
        
        header_layout.addWidget(self.back_btn)
        header_layout.addLayout(summary_vbox)
        header_layout.addStretch()
        
        # Overlay toggles
        self.toggle_settings_btn = QPushButton("⚙ Settings")
        self.toggle_settings_btn.clicked.connect(lambda: self.controller.settings_widget.setVisible(not self.controller.settings_widget.isVisible()))
        
        self.toggle_activity_btn = QPushButton("Activity")
        self.toggle_activity_btn.clicked.connect(lambda: self.controller.status_widget.setVisible(not self.controller.status_widget.isVisible()))
        
        header_layout.addWidget(self.toggle_settings_btn)
        header_layout.addWidget(self.toggle_activity_btn)
        
        layout.addLayout(header_layout)

        # Search Debounce Timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400)
        self.search_timer.timeout.connect(self.on_filter_changed)
        
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search title, author, DOI...")
        self.search_input.textChanged.connect(self.search_timer.start)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "PDF", "Pending", "Failed"])
        self.status_combo.currentTextChanged.connect(self.on_filter_changed)
        
        self.gen_combo = QComboBox()
        self.gen_combo.addItems(["All", "Seed", "Gen 1", "Gen 2+"])
        self.gen_combo.currentTextChanged.connect(self.on_filter_changed)
        
        self.showing_label = QLabel("Showing 0 of 0 papers")
        self.showing_label.setStyleSheet("color: #aaaaaa; margin-left: 10px;")
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(QLabel("Generation:"))
        filter_layout.addWidget(self.gen_combo)
        filter_layout.addWidget(self.showing_label)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Splitter for Table and Preview
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        # Table
        self.table = QTableView()
        self.table.setStyleSheet(
            "QTableView { background-color: #242424; alternate-background-color: #2a2a2a; } "
            "QTableView::item:selected { background-color: #293b38; border-left: 3px solid #35d07f; color: white; }"
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Checkbox
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive) # DOI
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)     # Title
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive) # Authors
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive) # Year
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive) # Status
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Interactive) # Network
        
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 60)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 150)
        
        self.table.setWordWrap(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        self.main_splitter.addWidget(self.table)
        
        self.preview_widget = PaperPreviewWidget(self)
        self.preview_widget.explore_past_callback = self.inline_explore_past
        self.preview_widget.explore_future_callback = self.inline_explore_future
        self.preview_widget.fetch_past_callback = lambda doi: self.controller.start_fetching_references([doi]) if hasattr(self.controller, "start_fetching_references") else None
        self.preview_widget.fetch_future_callback = lambda doi: self.controller.start_snowballing([doi]) if hasattr(self.controller, "start_snowballing") else None
        self.main_splitter.addWidget(self.preview_widget)
        
        self.main_splitter.setSizes([700, 300])
        layout.addWidget(self.main_splitter, 1)
        
        # Selection hook
        self.table.selectionModel() # This might be None until model is set. We'll set the hook in refresh_grid.

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_doi_btn = QPushButton("＋ Add DOI")
        self.add_doi_btn.setStyleSheet("background-color: #2CC985; color: black; font-weight: bold; padding: 6px 15px;")
        self.add_doi_btn.setToolTip("Manually enter a DOI to start a research session.")
        self.add_doi_btn.clicked.connect(self.add_manual_doi)
        
        self.clear_btn = QPushButton("Clear Workspace")
        self.clear_btn.setStyleSheet("color: #D9534F; background-color: transparent; border: 1px solid #D9534F;")
        self.clear_btn.clicked.connect(self.clear_workspace)
        
        btn_layout.addWidget(self.add_doi_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        
        # Progress Bar
        self.progressbar = QProgressBar()
        self.progressbar.setRange(0, 100)
        self.progressbar.setValue(0)
        self.progressbar.setTextVisible(True)
        self.progressbar.setFixedWidth(200)
        self.progressbar.hide()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_papers)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_papers)
        
        self.download_btn = QPushButton("↓ Download Selected")
        self.download_btn.setStyleSheet("background-color: #56B4E9; color: black; font-weight: bold; padding: 6px 15px;")
        self.download_btn.clicked.connect(self.trigger_download)
        
        btn_layout.addWidget(self.progressbar)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addWidget(self.download_btn)
        
        layout.addLayout(btn_layout)

    def refresh_grid(self):
        selected_doi = None
        if hasattr(self, 'proxy_model') and self.table.selectionModel():
            indexes = self.table.selectionModel().selectedRows()
            if indexes:
                proxy_index = indexes[0]
                source_index = self.proxy_model.mapToSource(proxy_index)
                selected_doi = self.model._data[source_index.row()][0]
                
        if self.current_mode == "root":
            raw_data = self.db.get_root_papers()
            self.breadcrumb_label.setText("Literature Workspace: Root (Seed Papers)")
            self.back_btn.hide()
        elif self.current_mode == "past":
            raw_data = self.db.get_past_references(self.current_doi)
            short_title = self.current_title[:40] + "..." if len(self.current_title) > 40 else self.current_title
            self.breadcrumb_label.setText(f"{short_title} > References")
            self.back_btn.show()
        elif self.current_mode == "future":
            raw_data = self.db.get_future_citations(self.current_doi)
            short_title = self.current_title[:40] + "..." if len(self.current_title) > 40 else self.current_title
            self.breadcrumb_label.setText(f"{short_title} > Cited By")
            self.back_btn.show()
            
        # Compute summary stats from ALL papers in DB
        all_papers = self.db.get_all_papers()
        seeds_count = sum(1 for row in all_papers if row[4] == 0) # generation
        refs_count = sum(1 for row in all_papers if row[4] != 0) 
        downloaded_count = sum(1 for row in all_papers if row[5] == 'downloaded')
        pending_count = sum(1 for row in all_papers if row[5] == 'pending')
        
        p_text = "paper" if len(all_papers) == 1 else "papers"
        pdf_text = "PDF" if downloaded_count == 1 else "PDFs"
        self.summary_label.setText(f"{len(all_papers)} {p_text} · {downloaded_count} {pdf_text} · {pending_count} pending")

        # Pack data
        clean_data = []
        for row in raw_data:
            doi = row[0] or ""
            
            # Format authors for table (APA style)
            authors_raw = row[2] or ""
            author_list = [a.strip() for a in authors_raw.split(',')] if authors_raw else []
            if len(author_list) > 2:
                authors_table = f"{author_list[0]} et al."
            elif len(author_list) == 2:
                authors_table = f"{author_list[0]} & {author_list[1]}"
            elif len(author_list) == 1:
                authors_table = author_list[0]
            else:
                authors_table = "Unknown Authors"
                
            raw_status = row[5] or ""
            if raw_status == "pending":
                status = "↓ Pending"
            elif raw_status == "downloaded":
                status = "✓ Ready"
            elif raw_status == "failed":
                status = "! Failed"
            elif raw_status == "no_pdf":
                status = "— Unavailable"
            else:
                status = raw_status
                
            # Get edge counts
            ref_c, cite_c = self.db.get_edge_counts(doi)
            ext_ref = row[6]
            ext_cite = row[7]
            
            ext_ref_str = f"{ext_ref}" if ext_ref is not None else "?"
            ext_cite_str = f"{ext_cite}" if ext_cite is not None else "?"
            
            network_str = f"← {ref_c}/{ext_ref_str}    {cite_c}/{ext_cite_str} →"
                
            clean_data.append([
                doi, row[1] or "", authors_table, row[3] or "", status, network_str, row[4]
            ])
        
        
        # Preserve checked_dois state across refreshes
        old_checked = getattr(self, 'model', None).checked_dois if hasattr(self, 'model') else set()
        self.model = PaperTableModel(clean_data, checked_dois=old_checked)
        
        if not hasattr(self, 'proxy_model'):
            self.proxy_model = PaperFilterProxyModel(self)
            self.proxy_model.setSourceModel(self.model)
            self.table.setModel(self.proxy_model)
            self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        else:
            self.proxy_model.setSourceModel(self.model)
            
        self.table.resizeRowsToContents()
        
        if selected_doi:
            for i, row in enumerate(self.model._data):
                if row[0] == selected_doi:
                    source_idx = self.model.index(i, 0)
                    proxy_idx = self.proxy_model.mapFromSource(source_idx)
                    self.table.selectionModel().select(proxy_idx, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                    break
        else:
            self.preview_widget.set_empty_state()
            
        self._update_showing_label()
        return len(raw_data)

    def on_filter_changed(self):
        if not hasattr(self, 'proxy_model'):
            return
            
        search_val = self.search_input.text().lower()
        status_val = self.status_combo.currentText()
        gen_val = self.gen_combo.currentText()
        
        logger.info("Filter applied", extra={
            "event": "filter_applied",
            "search": search_val,
            "status": status_val,
            "generation": gen_val
        })
            
        self.proxy_model.search_text = search_val
        self.proxy_model.status_filter = status_val
        self.proxy_model.gen_filter = gen_val
        self.proxy_model.invalidateFilter()
        self._update_showing_label()
        
    def _update_showing_label(self):
        if not hasattr(self, 'proxy_model'):
            return
        visible = self.proxy_model.rowCount()
        total = self.model.rowCount(None)
        if visible == total:
            p_text = "paper" if total == 1 else "papers"
            self.showing_label.setText(f"{total} {p_text}")
        else:
            self.showing_label.setText(f"Showing {visible} of {total} papers")
        
    def on_selection_changed(self, selected, deselected):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.preview_widget.set_empty_state()
            return
            
        proxy_index = indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        # Source index row directly maps to self.model._data if proxy doesn't shuffle it, 
        # but self.model._data now has `authors_table`. Wait, we need the original DOI to query the DB anyway.
        doi = self.model._data[source_index.row()][0]
        
        details = self.db.get_paper_details(doi)
        if details:
            edge_counts = self.db.get_edge_counts(doi)
            self.preview_widget.populate(doi, details, edge_counts)

    def navigate_back(self):
        if self.nav_stack:
            state = self.nav_stack.pop()
            self.current_mode = state["mode"]
            self.current_doi = state["doi"]
            self.current_title = state["title"]
            self.refresh_grid()

    def add_manual_doi(self):
        doi, ok = QInputDialog.getText(self, "Add Paper by DOI", "Enter the DOI (e.g. 10.1038/s41586-020-2649-2):")
        if ok and doi:
            doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
            if doi:
                self.db.add_paper(doi)
                self.db.add_discovery(doi, "manual", "seed", 0)
                self.refresh_grid()
                logger.info(f"Added manual DOI: {doi}", extra={"event": "ui_action", "action": "add_doi", "doi": doi})
                # Trigger metadata resolution so the title appears instantly
                if hasattr(self.controller, "start_metadata_resolution"):
                    self.controller.start_metadata_resolution()

    def _push_current_state(self):
        self.nav_stack.append({
            "mode": self.current_mode,
            "doi": self.current_doi,
            "title": self.current_title
        })
            
    def inline_explore_past(self, doi: str, title: str):
        self._push_current_state()
        self.current_mode = "past"
        self.current_doi = doi
        self.current_title = title or doi
        self.refresh_grid()

    def inline_explore_future(self, doi: str, title: str):
        self._push_current_state()
        self.current_mode = "future"
        self.current_doi = doi
        self.current_title = title or doi
        self.refresh_grid()

    # show_paper_info is replaced by on_selection_changed updating the preview

    def clear_workspace(self):

        reply = QMessageBox.question(
            self, 
            "Clear Workspace", 
            "Are you sure you want to clear the entire workspace? This will delete all discovered papers and lineage.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.clear_workspace()
            self.nav_stack.clear()
            self.current_mode = "root"
            self.current_doi = None
            self.current_title = None
            self.refresh_grid()
            logger.info("Workspace cleared.", extra={"event": "ui_action", "action": "clear_workspace"})

    def set_locked(self, locked: bool):
        self.add_doi_btn.setEnabled(not locked)
        self.clear_btn.setEnabled(not locked)
        self.download_btn.setEnabled(not locked)

    def set_progress(self, current: int, total: int):
        if total > 0:
            self.progressbar.show()
            pct = int((current / total) * 100)
            self.progressbar.setValue(pct)
            self.progressbar.setFormat(f"Downloading {current} of {total} ({pct}%)")
            if current >= total:
                self.progressbar.hide()
        else:
            self.progressbar.hide()

    def select_all_papers(self):
        if hasattr(self, 'model'):
            # Select all currently visible in proxy model, or all in base model?
            # It's usually better to select all in the current view (proxy model).
            if hasattr(self, 'proxy_model'):
                for i in range(self.proxy_model.rowCount()):
                    src_idx = self.proxy_model.mapToSource(self.proxy_model.index(i, 0))
                    doi = self.model._data[src_idx.row()][0]
                    self.model.checked_dois.add(doi)
                # Emit data changed for the whole column to update view
                self.model.dataChanged.emit(
                    self.model.index(0, 0), 
                    self.model.index(self.model.rowCount(None) - 1, 0), 
                    [Qt.CheckStateRole]
                )

    def deselect_all_papers(self):
        if hasattr(self, 'model'):
            self.model.checked_dois.clear()
            self.model.dataChanged.emit(
                self.model.index(0, 0), 
                self.model.index(self.model.rowCount(None) - 1, 0), 
                [Qt.CheckStateRole]
            )
            
    def trigger_download(self):
        if hasattr(self, 'model'):
            selected_dois = list(self.model.checked_dois)
            if hasattr(self.controller, "start_download"):
                self.controller.start_download(selected_dois=selected_dois)
