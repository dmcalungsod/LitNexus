import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QApplication
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from src.downloader import settings_manager

class PaperDetailsDialog(QDialog):
    def __init__(self, doi, title, authors, year, abstract, pdf_status, ref_count, cited_count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paper Details")
        self.setMinimumWidth(500)
        self.setMaximumWidth(600)
        self.doi = doi
        self.title = title or "Unknown Title"
        self.authors = authors or "Unknown Authors"
        self.year = year or "Unknown Year"
        self.abstract = abstract or "No abstract available."
        self.pdf_status = pdf_status or "pending"
        self.ref_count = ref_count
        self.cited_count = cited_count
        
        self.explore_past_callback = None
        self.explore_future_callback = None
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        year_label = QLabel(str(self.year))
        year_label.setStyleSheet("font-size: 14px; color: #aaaaaa;")
        
        layout.addWidget(title_label)
        layout.addWidget(year_label)
        
        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet("color: #444;")
        layout.addWidget(div1)
        
        # DOI Row
        doi_layout = QHBoxLayout()
        doi_header = QLabel("DOI")
        doi_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        layout.addWidget(doi_header)
        
        doi_val = QLabel(self.doi)
        doi_val.setStyleSheet("font-size: 13px; font-family: monospace;")
        doi_layout.addWidget(doi_val)
        doi_layout.addStretch()
        
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.doi))
        
        open_btn = QPushButton("Open ↗")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://doi.org/{self.doi}")))
        
        doi_layout.addWidget(copy_btn)
        doi_layout.addWidget(open_btn)
        layout.addLayout(doi_layout)
        
        # Authors Row
        auth_header = QLabel("AUTHORS")
        auth_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        layout.addWidget(auth_header)
        
        author_list = [a.strip() for a in self.authors.split(',')]
        if len(author_list) > 4:
            short_authors = ", ".join(author_list[:3])
            more_count = len(author_list) - 3
            
            self.auth_val = QLabel()
            self.auth_val.setWordWrap(True)
            self.auth_val.setStyleSheet("font-size: 13px;")
            self.auth_val.setText(f'{short_authors}, <a href="#expand" style="color: #56B4E9; text-decoration: none;"><b>+ {more_count} more</b></a>')
            
            def on_author_click(link):
                self.auth_val.setText(", ".join(author_list))
                
            self.auth_val.linkActivated.connect(on_author_click)
        else:
            self.auth_val = QLabel(self.authors)
            self.auth_val.setWordWrap(True)
            self.auth_val.setStyleSheet("font-size: 13px;")
            
        layout.addWidget(self.auth_val)
        
        # Status
        status_header = QLabel("STATUS")
        status_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        layout.addWidget(status_header)
        
        status_text = "⚪ PDF Unavailable"
        if self.pdf_status == "downloaded":
            status_text = "🟢 PDF Downloaded"
        elif self.pdf_status == "pending":
            status_text = "🟡 PDF Pending"
        elif self.pdf_status == "failed":
            status_text = "🔴 Download Failed"
            
        status_label = QLabel(status_text)
        status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(status_label)
        
        # Abstract
        abs_header = QLabel("ABSTRACT")
        abs_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #888888;")
        layout.addWidget(abs_header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #444; background-color: #222; }")
        
        abs_val = QLabel(self.abstract)
        abs_val.setWordWrap(True)
        abs_val.setStyleSheet("font-size: 13px; line-height: 1.4; padding: 5px;")
        abs_val.setAlignment(Qt.AlignTop)
        scroll.setWidget(abs_val)
        
        layout.addWidget(scroll)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        
        if self.pdf_status == "downloaded":
            open_pdf_btn = QPushButton("Open PDF")
            open_pdf_btn.setStyleSheet("background-color: #2CC985; color: black; font-weight: bold;")
            open_pdf_btn.clicked.connect(self.open_pdf)
            btn_layout.addWidget(open_pdf_btn)
            
        btn_layout.addStretch()
        
        if self.ref_count > 0:
            ref_btn = QPushButton(f"References {self.ref_count}")
            ref_btn.clicked.connect(self.on_references_clicked)
            btn_layout.addWidget(ref_btn)
            
        if self.cited_count > 0:
            cite_btn = QPushButton(f"Cited By {self.cited_count}")
            cite_btn.clicked.connect(self.on_cited_clicked)
            btn_layout.addWidget(cite_btn)
            
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
    def on_references_clicked(self):
        if self.explore_past_callback:
            self.explore_past_callback()
        self.accept()
        
    def on_cited_clicked(self):
        if self.explore_future_callback:
            self.explore_future_callback()
        self.accept()

    def open_pdf(self):
        settings = settings_manager.read_config_raw() or {}
        out_dir = settings.get("output_dir", str(Path.home() / "Downloads" / "LitNexus"))
        
        safe_doi = self.doi.replace('/', '_').replace('\\', '_')
        pdf_path = Path(out_dir) / f"{safe_doi}.pdf"
        
        if pdf_path.exists():
            if os.name == 'nt':
                os.startfile(str(pdf_path))
            elif os.name == 'posix':
                subprocess.call(['open', str(pdf_path)])
        else:
            for f in Path(out_dir).glob("*.pdf"):
                if safe_doi in f.name:
                    if os.name == 'nt':
                        os.startfile(str(f))
                    elif os.name == 'posix':
                        subprocess.call(['open', str(f)])
                    return
