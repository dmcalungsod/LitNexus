import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QApplication,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from src.downloader import settings_manager
from src.downloader.logging_config import get_logger

logger = get_logger(__name__)


class PaperPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace = parent

        self.doi = None
        self.title = None
        self.explore_past_callback = None
        self.explore_future_callback = None
        self.fetch_past_callback = None
        self.fetch_future_callback = None

        self.setup_ui()
        self.set_empty_state()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.empty_label = QLabel("No paper selected.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #777; font-size: 14px;")

        # Main Scroll Area
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        # Content Container
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)

        # 1. PAPER HEADER
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.author_year_label = QLabel()
        self.author_year_label.setStyleSheet("font-size: 13px; color: #aaaaaa;")
        self.author_year_label.setWordWrap(True)
        self.author_year_label.setTextFormat(Qt.RichText)
        self.author_year_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.author_year_label.linkActivated.connect(self.on_author_link_activated)

        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.author_year_label)

        # DOI
        self.doi_label = QLabel("DOI")
        self.doi_label.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #888888; margin-top: 10px;"
        )
        content_layout.addWidget(self.doi_label)

        self.doi_val = QLabel()
        self.doi_val.setStyleSheet("font-size: 13px; color: #56B4E9;")
        self.doi_val.setOpenExternalLinks(True)
        content_layout.addWidget(self.doi_val)

        # 2. HERO ACTIONS
        hero_actions_layout = QHBoxLayout()
        self.hero_action_btn = QPushButton("Open PDF")
        self.hero_action_btn.clicked.connect(self.on_hero_action_clicked)

        self.copy_btn = QPushButton("Copy DOI")
        self.copy_btn.setStyleSheet("padding: 5px 15px;")
        self.copy_btn.clicked.connect(self.copy_doi)

        hero_actions_layout.addWidget(self.hero_action_btn)
        hero_actions_layout.addWidget(self.copy_btn)
        hero_actions_layout.addStretch()
        content_layout.addLayout(hero_actions_layout)

        # Divider 1
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet("color: #444; margin-top: 10px; margin-bottom: 10px;")
        content_layout.addWidget(div1)

        # 3. ABSTRACT
        abs_header_layout = QHBoxLayout()
        abs_header = QLabel("ABSTRACT")
        abs_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")

        self.toggle_abs_btn = QPushButton("▾")
        self.toggle_abs_btn.setFixedSize(20, 20)
        self.toggle_abs_btn.setStyleSheet("border: none; color: #aaa;")
        self.toggle_abs_btn.clicked.connect(self.toggle_abstract)

        abs_header_layout.addWidget(abs_header)
        abs_header_layout.addWidget(self.toggle_abs_btn)
        abs_header_layout.addStretch()
        content_layout.addLayout(abs_header_layout)

        self.abs_val = QLabel()
        self.abs_val.setWordWrap(True)
        self.abs_val.setStyleSheet("font-size: 13px; line-height: 1.4; color: #ccc;")
        self.abs_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_layout.addWidget(self.abs_val)

        # Divider 2
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("color: #444; margin-top: 10px; margin-bottom: 10px;")
        content_layout.addWidget(div2)

        # 4. CITATION NETWORK
        net_header = QLabel("CITATION NETWORK")
        net_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        content_layout.addWidget(net_header)

        self.generation_label = QLabel()
        self.generation_label.setStyleSheet("font-size: 13px; margin-bottom: 10px;")
        content_layout.addWidget(self.generation_label)

        # References layout
        self.ref_info_label = QLabel()
        self.ref_info_label.setStyleSheet("font-size: 13px; color: #aaa;")
        content_layout.addWidget(self.ref_info_label)

        self.ref_action_btn = QPushButton()
        self.ref_action_btn.setStyleSheet("padding: 5px 15px; text-align: left;")
        self.ref_action_btn.clicked.connect(self.on_references_action)

        ref_btn_layout = QHBoxLayout()
        ref_btn_layout.addWidget(self.ref_action_btn)
        ref_btn_layout.addStretch()
        content_layout.addLayout(ref_btn_layout)

        # Citations layout
        self.cite_info_label = QLabel()
        self.cite_info_label.setStyleSheet("font-size: 13px; color: #aaa; margin-top: 10px;")
        content_layout.addWidget(self.cite_info_label)

        self.cite_action_btn = QPushButton()
        self.cite_action_btn.setStyleSheet("padding: 5px 15px; text-align: left;")
        self.cite_action_btn.clicked.connect(self.on_citations_action)

        cite_btn_layout = QHBoxLayout()
        cite_btn_layout.addWidget(self.cite_action_btn)
        cite_btn_layout.addStretch()
        content_layout.addLayout(cite_btn_layout)

        # Divider 3
        div3 = QFrame()
        div3.setFrameShape(QFrame.HLine)
        div3.setStyleSheet("color: #444; margin-top: 10px; margin-bottom: 10px;")
        content_layout.addWidget(div3)

        # 5. PROVENANCE
        prov_header = QLabel("PROVENANCE")
        prov_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        content_layout.addWidget(prov_header)

        self.provenance_text = QLabel()
        self.provenance_text.setWordWrap(True)
        self.provenance_text.setStyleSheet("font-size: 12px; color: #aaa;")
        content_layout.addWidget(self.provenance_text)

        content_layout.addStretch()

        self.main_scroll.setWidget(self.content_widget)

        self.layout.addWidget(self.empty_label)
        self.layout.addWidget(self.main_scroll)

    def set_empty_state(self):
        self.empty_label.show()
        self.main_scroll.hide()

    def copy_doi(self):
        if self.doi:
            QApplication.clipboard().setText(self.doi)
            logger.info(
                f"Copied DOI: {self.doi}",
                extra={"event": "ui_action", "action": "copy_doi", "doi": self.doi},
            )

    def on_author_link_activated(self, link):
        logger.info(
            f"Toggled authors: {link}",
            extra={"event": "ui_action", "action": "toggle_authors", "link": link},
        )
        if link == "show_more":
            self.author_year_label.setText(
                f"{self.full_authors} <a href='show_less' style='color: #56B4E9; text-decoration: none;'>[show less]</a> · {self.year}"
            )
        elif link == "show_less":
            author_list = [a.strip() for a in self.full_authors.split(",")]
            short_authors = f"{', '.join(author_list[:3])}, <a href='show_more' style='color: #56B4E9; text-decoration: none;'>+ {len(author_list) - 3} more</a>"
            self.author_year_label.setText(f"{short_authors} · {self.year}")

    def toggle_abstract(self):
        is_visible = self.abs_val.isVisible()
        self.abs_val.setVisible(not is_visible)
        self.toggle_abs_btn.setText("▸" if is_visible else "▾")
        logger.info(
            f"Toggled abstract visibility: {not is_visible}",
            extra={"event": "ui_action", "action": "toggle_abstract", "visible": not is_visible},
        )

    def on_hero_action_clicked(self):
        logger.info(
            f"Hero action clicked for {self.doi}",
            extra={
                "event": "ui_action",
                "action": "hero_action",
                "status": self.pdf_status,
                "doi": self.doi,
            },
        )
        if self.pdf_status == "downloaded":
            self.open_pdf()
        elif self.pdf_status == "pending":
            if hasattr(self.workspace.controller, "start_download"):
                self.workspace.controller.start_download(selected_dois=[self.doi])

    def _setup_network_action(self, btn, label, prefix, loc, ext, status):
        # Determine button behavior and text
        btn_enabled = True

        if ext is None:
            # Unknown total
            label.setText(f"{prefix}\n{loc} in workspace · Total unknown")
            if loc > 0:
                btn.setText(f"View {prefix} ({loc})")
                action_type = "view"
            elif status == "complete":
                btn.setText(f"View {prefix} (0)")
                action_type = "view"
            else:
                btn.setText(f"Fetch {prefix}")
                action_type = "fetch"
        elif ext == 0:
            label.setText(f"{prefix}\n0 in workspace · 0 total")
            btn.setText(f"No {prefix}")
            btn_enabled = False
            action_type = "none"
        else:
            label.setText(f"{prefix}\n{loc} in workspace · {ext} total")
            if loc > 0:
                btn.setText(f"View {prefix} ({loc})")
                action_type = "view"
            elif status == "complete":
                btn.setText(f"View {prefix} (0)")
                action_type = "view"
            else:
                btn.setText(f"Fetch {prefix} ({ext})")
                action_type = "fetch"

        btn.setEnabled(btn_enabled)
        return action_type

    def populate(self, doi: str, details: tuple, edge_counts: tuple):
        self.empty_label.hide()
        self.main_scroll.show()

        self.doi = doi
        (
            title,
            authors,
            year,
            abstract,
            pdf_status,
            gen,
            ext_ref,
            ext_cite,
            ref_status,
            cite_status,
        ) = details
        loc_ref, loc_cite = edge_counts

        self.title = title or "Unknown Title"
        self.title_label.setText(self.title)

        self.full_authors = authors or "Unknown Authors"
        author_list = [a.strip() for a in self.full_authors.split(",")]
        self.year = year or "Unknown Year"

        if len(author_list) > 3:
            short_authors = f"{', '.join(author_list[:3])}, <a href='show_more' style='color: #56B4E9; text-decoration: none;'>+ {len(author_list) - 3} more</a>"
            self.author_year_label.setText(f"{short_authors} · {self.year}")
        else:
            self.author_year_label.setText(f"{self.full_authors} · {self.year}")

        self.doi_val.setText(
            f'<a href="https://doi.org/{self.doi}" style="color: #56B4E9; text-decoration: none;">{self.doi}</a>'
        )

        self.abs_val.setText(abstract or "No abstract available.")

        # Hero Action
        self.pdf_status = pdf_status
        self.hero_action_btn.setEnabled(True)
        if pdf_status == "downloaded":
            self.hero_action_btn.setText("Open PDF")
            self.hero_action_btn.setStyleSheet(
                "background-color: #2CC985; color: black; font-weight: bold; padding: 5px 15px; border-radius: 4px;"
            )
        elif pdf_status == "pending":
            self.hero_action_btn.setText("↓ Download PDF")
            self.hero_action_btn.setStyleSheet(
                "background-color: #0D6EFD; color: white; border: none; font-weight: bold; padding: 5px 15px; border-radius: 4px;"
            )
        elif pdf_status == "failed":
            self.hero_action_btn.setText("! Download Failed")
            self.hero_action_btn.setStyleSheet(
                "background-color: transparent; color: #D9534F; border: 1px solid #D9534F; font-weight: bold; padding: 5px 15px; border-radius: 4px;"
            )
        else:
            self.hero_action_btn.setText("— PDF Unavailable")
            self.hero_action_btn.setStyleSheet(
                "background-color: transparent; color: #555; border: 1px solid #555; font-weight: bold; padding: 5px 15px; border-radius: 4px;"
            )
            self.hero_action_btn.setEnabled(False)

        # Network Vis
        gen_text = "Generation 0 · Seed" if gen == 0 else f"Generation {gen}"
        self.generation_label.setText(gen_text)

        self.ref_action_type = self._setup_network_action(
            self.ref_action_btn, self.ref_info_label, "References", loc_ref, ext_ref, ref_status
        )

        self.cite_action_type = self._setup_network_action(
            self.cite_action_btn, self.cite_info_label, "Cited by", loc_cite, ext_cite, cite_status
        )

        # Provenance Fetch
        db = self.workspace.db
        prov_records = db.get_provenance(doi)

        if not prov_records:
            if gen == 0:
                self.provenance_text.setText("Seed paper\nAdded manually")
            else:
                self.provenance_text.setText("Unknown discovery path")
        else:
            if len(prov_records) == 1:
                direction = prov_records[0][1]
                s_title = prov_records[0][2] or prov_records[0][0]
                self.provenance_text.setText(f"via {direction.capitalize()} from:\n{s_title}")
            else:
                lines = []
                for i, (s_doi, direction, s_title) in enumerate(prov_records):
                    s_title = s_title or s_doi
                    prefix = "First discovered via" if i == 0 else "Also discovered via"
                    lines.append(f"{prefix}\n{direction.capitalize()} → {s_title}\n")
                self.provenance_text.setText("\n".join(lines).strip())

    def on_references_action(self):
        logger.info(
            f"References action: {self.ref_action_type}",
            extra={
                "event": "ui_action",
                "action": "ref_action",
                "type": self.ref_action_type,
                "doi": self.doi,
            },
        )
        if self.ref_action_type == "view":
            if self.explore_past_callback:
                self.explore_past_callback(self.doi, self.title)
        elif self.ref_action_type == "fetch":
            if self.fetch_past_callback:
                self.fetch_past_callback(self.doi)

    def on_citations_action(self):
        logger.info(
            f"Citations action: {self.cite_action_type}",
            extra={
                "event": "ui_action",
                "action": "cite_action",
                "type": self.cite_action_type,
                "doi": self.doi,
            },
        )
        if self.cite_action_type == "view":
            if self.explore_future_callback:
                self.explore_future_callback(self.doi, self.title)
        elif self.cite_action_type == "fetch":
            if self.fetch_future_callback:
                self.fetch_future_callback(self.doi)

    def open_pdf(self):
        # Prefer the exact stored local filepath from the DB. Fall back to previous heuristic.
        try:
            db = self.workspace.db
            stored = None
            try:
                stored = db.get_paper_filepath(self.doi)
            except Exception:
                stored = None

            if stored:
                p = Path(stored)
                logger.info(
                    f"Opening PDF (stored path) for {self.doi}",
                    extra={
                        "event": "ui_action",
                        "action": "open_pdf",
                        "doi": self.doi,
                        "path": str(p),
                    },
                )
                if p.exists():
                    if os.name == "nt":
                        os.startfile(str(p))
                    elif os.name == "posix":
                        subprocess.call(["open", str(p)])
                    return
        except Exception:
            logger.exception(
                "Error while retrieving stored PDF path",
                extra={"event": "open_pdf_error", "doi": self.doi},
            )

        # Fallback: try legacy heuristic based on output_dir and safe DOI
        settings = settings_manager.read_config_raw() or {}
        out_dir = settings.get("output_dir", str(Path.home() / "Downloads" / "LitNexus"))
        safe_doi = self.doi.replace("/", "_").replace("\\", "_")
        pdf_path = Path(out_dir) / f"{safe_doi}.pdf"

        logger.info(
            f"Opening PDF (fallback) for {self.doi}",
            extra={
                "event": "ui_action",
                "action": "open_pdf",
                "doi": self.doi,
                "path": str(pdf_path),
            },
        )

        if pdf_path.exists():
            if os.name == "nt":
                os.startfile(str(pdf_path))
            elif os.name == "posix":
                subprocess.call(["open", str(pdf_path)])
            return

        for f in Path(out_dir).glob("*.pdf"):
            if safe_doi in f.name:
                if os.name == "nt":
                    os.startfile(str(f))
                elif os.name == "posix":
                    subprocess.call(["open", str(f)])
                return
