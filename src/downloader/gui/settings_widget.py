from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QCheckBox, 
    QSlider, QPushButton, QScrollArea, QFormLayout, QFrame, QHBoxLayout
)
from PySide6.QtCore import Qt

from src.downloader import settings_manager
from pathlib import Path
from src.downloader.logging_config import get_logger

logger = get_logger(__name__)

class SettingsWidget(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        vbox = QVBoxLayout(content)
        self.form = QFormLayout()
        vbox.addLayout(self.form)
        vbox.addStretch()
        
        # Output Dir
        self.output_dir = QLineEdit()
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.controller.browse_output_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.output_dir)
        dir_layout.addWidget(self.browse_btn)
        self.form.addRow("Output Directory:", dir_layout)
        
        # Email
        self.email_input, self.email_show = self._create_secure_input()
        self.form.addRow("Unpaywall Email:", self.email_input)
        self.form.addRow("", self.email_show)
        
        # CORE API Key
        self.core_input, self.core_show = self._create_secure_input()
        self.form.addRow("CORE API Key:", self.core_input)
        self.form.addRow("", self.core_show)
        
        # OpenAlex API Key
        self.openalex_input, self.openalex_show = self._create_secure_input()
        self.form.addRow("OpenAlex API Key:", self.openalex_input)
        self.form.addRow("", self.openalex_show)
        
        # Bypass SSL
        self.ssl_checkbox = QCheckBox("Bypass SSL verification")
        self.form.addRow("", self.ssl_checkbox)
        
        # Parallel Downloads
        self.parallel_lbl = QLabel("Parallel Downloads: 10")
        self.parallel_slider = QSlider(Qt.Horizontal)
        self.parallel_slider.setRange(1, 20)
        self.parallel_slider.setValue(10)
        self.parallel_slider.valueChanged.connect(
            lambda v: self.parallel_lbl.setText(f"Parallel Downloads: {v}")
        )
        self.form.addRow(self.parallel_lbl, self.parallel_slider)
        
        # Action Buttons
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        
        self.clear_btn = QPushButton("Clear Settings")
        self.clear_btn.clicked.connect(self.clear_settings)
        
        self.form.addRow(self.save_btn)
        self.form.addRow(self.clear_btn)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _create_secure_input(self):
        layout = QHBoxLayout()
        input_field = QLineEdit()
        input_field.setEchoMode(QLineEdit.Password)
        show_cb = QCheckBox("Show")
        show_cb.stateChanged.connect(
            lambda state, field=input_field: field.setEchoMode(
                QLineEdit.Normal if state else QLineEdit.Password
            )
        )
        layout.addWidget(input_field)
        return layout, show_cb
        
    def _get_field(self, layout):
        return layout.itemAt(0).widget()

    def load_settings(self):
        settings = settings_manager.read_config_raw() or {}
        default_dir = str(Path.home() / "Downloads" / "LitNexus")
        
        self.output_dir.setText(settings.get("output_dir", default_dir))
        self._get_field(self.email_input).setText(settings.get("email", ""))
        self._get_field(self.core_input).setText(settings.get("core_api_key", ""))
        self._get_field(self.openalex_input).setText(settings.get("openalex_api_key", ""))
        self.ssl_checkbox.setChecked(not settings.get("verify_ssl", True))
        
        max_workers = settings.get("max_workers", 10)
        self.parallel_slider.setValue(max_workers)

    def save_settings(self):
        settings = {
            "output_dir": self.output_dir.text(),
            "email": self._get_field(self.email_input).text(),
            "core_api_key": self._get_field(self.core_input).text(),
            "openalex_api_key": self._get_field(self.openalex_input).text(),
            "verify_ssl": not self.ssl_checkbox.isChecked(),
            "max_workers": self.parallel_slider.value(),
        }
        settings_manager.write_config_raw(settings)
        logger.info("Settings saved.", extra={"event": "ui_action", "action": "save_settings"})

    def clear_settings(self):
        settings_manager.delete_config_raw()
        self.load_settings()
        logger.info("Settings cleared.", extra={"event": "ui_action", "action": "clear_settings"})

    def set_locked(self, locked: bool):
        self.setEnabled(not locked)
