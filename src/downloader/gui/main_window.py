import logging
import os
import queue
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QMessageBox, QSplitter, QFileDialog
from PySide6.QtCore import Qt, QTimer, QSettings

from src.downloader import settings_manager, parsers
from src.downloader.download_manager import DownloadManager
from src.downloader.snowball_engine import SnowballEngine
from src.downloader.metadata_resolver import MetadataResolverEngine
from src.downloader.reference_engine import ReferenceEngine
from src.downloader.database import DatabaseManager
from src.downloader.gui.settings_widget import SettingsWidget
from src.downloader.gui.workspace_widget import WorkspaceWidget
from src.downloader.gui.status_widget import StatusWidget
from src.downloader.logging_config import get_logger, start_operation

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LitNexus - Snowball Workspace")
        self.resize(1400, 800)

        self.is_downloading = False
        self.download_manager = None
        self.total_dois_to_download = 0
        self.processed_doi_count = 0

        self.progress_queue = queue.Queue()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_progress_queue)

        self.setup_ui()

        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; color: #ffffff; }
            QWidget { background-color: #2b2b2b; color: #ffffff; }
            QPushButton { background-color: #3b3b3b; border: 1px solid #555; padding: 5px; border-radius: 4px; }
            QPushButton:hover { background-color: #4b4b4b; }
            QTableView { background-color: #1e1e1e; alternate-background-color: #2a2a2a; color: #d4d4d4; gridline-color: #333; border: 1px solid #444; }
            QHeaderView::section { background-color: #2a2a2a; padding: 4px; border: 1px solid #333; font-weight: normal; }
            QTextEdit { background-color: #1e1e1e; border: 1px solid #444; }
            QLineEdit, QSlider::groove:horizontal { background-color: #3b3b3b; border: 1px solid #555; }
            QProgressBar { text-align: center; border: 1px solid #555; border-radius: 4px; }
            QProgressBar::chunk { background-color: #2CC985; }
        """)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)

        self.settings_widget = SettingsWidget(self)
        self.workspace_widget = WorkspaceWidget(self)
        self.status_widget = StatusWidget(self)

        splitter.addWidget(self.settings_widget)
        splitter.addWidget(self.workspace_widget)
        splitter.addWidget(self.status_widget)

        self.settings_widget.setVisible(False)
        self.status_widget.setVisible(False)

        splitter.setSizes([300, 700, 400])
        layout.addWidget(splitter)

    # --- Core Logic ---
    def start_download(self, selected_dois=None):
        if self.is_downloading:
            return

        # If a selection list was provided (even if empty), use it
        if selected_dois is not None:
            if not selected_dois:
                QMessageBox.information(self, "No Selection", "No papers selected. Please check the boxes for papers you want to download.")
                return
            pending = [
                row[0] for row in self.workspace_widget.db.get_all_papers() 
                if row[5] == "pending" and row[0] in selected_dois
            ]
        else:
            # Fallback to downloading all pending (used by hero action button)
            pending = [
                row[0] for row in self.workspace_widget.db.get_all_papers() if row[5] == "pending"
            ]

        if not pending:
            logger.info("No pending papers to download.", extra={"event": "download_start_empty"})
            if selected_dois is not None:
                QMessageBox.information(self, "Download Complete", "None of the selected papers were in a 'pending' state.")
            self._finish_task("download_empty")
            return

        self.is_downloading = True
        self.toggle_ui_lock(True)
        self.processed_doi_count = 0
        self.total_dois_to_download = len(pending)

        op_id = start_operation()

        logger.info(
            f"Starting download of {self.total_dois_to_download} pending papers...",
            extra={"event": "download_start", "count": self.total_dois_to_download},
        )
        self.workspace_widget.set_progress(0, self.total_dois_to_download)

        settings = settings_manager.read_config_raw() or {}
        out_dir = settings.get("output_dir", str(Path.home() / "Downloads" / "LitNexus"))
        failed_path = Path(out_dir) / "failed_dois.txt"

        self.download_manager = DownloadManager(
            settings=settings,
            progress_queue=self.progress_queue,
            dois=pending,
            failed_dois_path=failed_path,
        )
        self.download_manager.start()
        self.poll_timer.start(100)

    def cancel_download(self):
        if self.download_manager and self.download_manager.is_alive():
            logger.warning("Cancel request received...", extra={"event": "download_cancel_request"})
            self.download_manager.cancel_download()

    def start_snowballing(self, dois: list[str]):
        if self.is_downloading:
            logger.warning(
                "Cannot start snowballing while task is running.", extra={"event": "task_conflict"}
            )
            return

        op_id = start_operation()
        logger.info("Starting snowballing.", extra={"event": "snowball_start", "dois": dois})
        self.last_fetched_dois = dois

        self.is_downloading = True
        self.toggle_ui_lock(True)

        settings = settings_manager.read_config_raw() or {}
        email = settings.get("email", "")
        api_key = settings.get("openalex_api_key", None)

        self.snowball_manager = SnowballEngine(
            dois=dois,
            db_manager=self.workspace_widget.db,
            progress_queue=self.progress_queue,
            openalex_api_key=api_key,
            email=email,
        )
        self.snowball_manager.start()
        self.poll_timer.start(100)

    def start_fetching_references(self, dois: list[str]):
        if self.is_downloading:
            logger.warning(
                "Cannot fetch references while task is running.", extra={"event": "task_conflict"}
            )
            return

        op_id = start_operation()
        logger.info(
            "Starting reference fetch.", extra={"event": "reference_fetch_start", "dois": dois}
        )
        self.last_fetched_dois = dois

        self.is_downloading = True
        self.toggle_ui_lock(True)

        settings = settings_manager.read_config_raw() or {}
        email = settings.get("email", "")

        self.reference_manager = ReferenceEngine(
            dois=dois,
            db_manager=self.workspace_widget.db,
            progress_queue=self.progress_queue,
            email=email,
        )
        self.reference_manager.start()
        self.poll_timer.start(100)

    def start_metadata_resolution(self):
        # Fetch naked DOIs
        papers = self.workspace_widget.db.get_all_papers()
        # Tuple is (doi, title, year, gen, status)
        naked_dois = [row[0] for row in papers if not row[1]]  # No title

        if not naked_dois:
            return

        op_id = start_operation()
        logger.info(
            "Starting metadata resolution.",
            extra={"event": "metadata_resolve_start", "count": len(naked_dois)},
        )

        settings = settings_manager.read_config_raw() or {}
        email = settings.get("email", "")

        self.resolver_manager = MetadataResolverEngine(
            dois=naked_dois,
            db_manager=self.workspace_widget.db,
            progress_queue=self.progress_queue,
            email=email,
        )
        self.resolver_manager.start()
        self.poll_timer.start(100)

    def poll_progress_queue(self):
        try:
            while not self.progress_queue.empty():
                msg = self.progress_queue.get_nowait()
                status = msg.get("status")

                if status == "start":
                    logger.info(msg.get("message"), extra={"event": "task_message"})
                elif status == "complete":
                    logger.info(
                        f"Download Complete: {msg.get('message')}", extra={"event": "task_complete"}
                    )
                elif status == "cancelled":
                    logger.warning(
                        f"Download Cancelled: {msg.get('message')}",
                        extra={"event": "task_cancelled"},
                    )
                elif status == "critical_error":
                    logger.error(
                        f"Critical error: {msg.get('message')}", extra={"event": "task_error"}
                    )
                elif status in [
                    "finished",
                    "snowball_finished",
                    "resolver_finished",
                    "reference_finished",
                ]:
                    self._finish_task(status)
                    return
                elif (
                    status == "snowball_log"
                    or status == "resolver_log"
                    or status == "reference_log"
                ):
                    logger.info(msg.get("message"), extra={"event": "task_log"})
                elif status == "resolver_item_done":
                    self.workspace_widget.refresh_grid()
                else:
                    self.processed_doi_count += 1
                    doi = msg.get("doi", "Unknown")
                    if status == "success":
                        logger.info(
                            f"Download success: {doi}",
                            extra={"event": "download_success", "doi": doi},
                        )
                        # Persist downloaded filepath and mark as downloaded
                        filepath = msg.get("filename")
                        try:
                            if filepath:
                                self.workspace_widget.db.update_paper_filepath(doi, filepath)
                        except Exception:
                            logger.exception(
                                "Failed to store downloaded filepath",
                                extra={"event": "db_update_error", "doi": doi},
                            )
                        self.workspace_widget.db.update_pdf_status(doi, "downloaded")
                    elif status == "skipped":
                        logger.info(
                            f"Download skipped: {doi}",
                            extra={"event": "download_skipped", "doi": doi},
                        )
                        filepath = msg.get("filename")
                        try:
                            if filepath:
                                self.workspace_widget.db.update_paper_filepath(doi, filepath)
                        except Exception:
                            logger.exception(
                                "Failed to store skipped filepath",
                                extra={"event": "db_update_error", "doi": doi},
                            )
                        self.workspace_widget.db.update_pdf_status(doi, "downloaded")
                    else:
                        logger.warning(
                            f"Download failed: {doi}",
                            extra={"event": "download_failed", "doi": doi},
                        )

                    self.workspace_widget.set_progress(
                        self.processed_doi_count, self.total_dois_to_download
                    )
                    self.workspace_widget.refresh_grid()

        except queue.Empty:
            pass

    def _finish_task(self, task_type: str):
        self.poll_timer.stop()
        self.is_downloading = False
        self.toggle_ui_lock(False)
        self.workspace_widget.refresh_grid()
        self.download_manager = None
        logger.info(
            f"Task completed: {task_type}",
            extra={"event": "task_completed_overall", "task_type": task_type},
        )

        settings = settings_manager.read_config_raw() or {}

        # Auto-navigate if exactly 1 paper was fetched
        navigated = False
        if hasattr(self, "last_fetched_dois") and len(self.last_fetched_dois) == 1:
            doi = self.last_fetched_dois[0]
            details = self.workspace_widget.db.get_paper_details(doi)
            title = details[0] if details else doi

            if task_type == "snowball_finished":
                self.workspace_widget.inline_explore_future(doi, title)
                navigated = True
            elif task_type == "reference_finished":
                self.workspace_widget.inline_explore_past(doi, title)
                navigated = True

        if settings.get("show_completion_popup", True) and not navigated:
            if task_type == "snowball_finished":
                QMessageBox.information(
                    self,
                    "Snowball Complete",
                    "Citation snowballing has finished discovering new papers.",
                )
            elif task_type == "reference_finished":
                QMessageBox.information(
                    self,
                    "References Complete",
                    "Finished fetching references for the selected papers.",
                )
            elif task_type == "resolver_finished":
                QMessageBox.information(
                    self, "Metadata Complete", "Finished resolving missing metadata for papers."
                )
            elif task_type != "download_empty":
                QMessageBox.information(
                    self, "Download Complete", "All download tasks have finished."
                )

    # --- Utilities ---
    def toggle_ui_lock(self, locked: bool):
        from PySide6.QtWidgets import QApplication

        if locked:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

        self.settings_widget.set_locked(locked)
        self.workspace_widget.set_locked(locked)
        self.status_widget.set_locked(locked)

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.settings_widget._get_field(self.settings_widget.output_dir).setText(dir_path)

    def open_output_folder(self):
        settings = settings_manager.read_config_raw() or {}
        out_dir = settings.get("output_dir", str(Path.home() / "Downloads" / "LitNexus"))
        logger.info(
            "Opening output folder", extra={"event": "open_output_folder", "out_dir": out_dir}
        )
        if os.name == "nt":
            os.startfile(out_dir)
        elif os.name == "posix":
            subprocess.call(["open", out_dir])

    def retry_failed_dois(self):
        logger.warning(
            "Retry failed is currently unmapped. Load failed_dois.txt via Seed PDF.",
            extra={"event": "ui_warning_unmapped"},
        )

    def view_failed(self):
        logger.warning(
            "View failed is currently unmapped. Open failed_dois.txt in output dir.",
            extra={"event": "ui_warning_unmapped"},
        )

    def closeEvent(self, event):
        settings = QSettings("PDFRetriever", "Workspace")
        settings.setValue("main_splitter", self.workspace_widget.main_splitter.saveState())
        super().closeEvent(event)
