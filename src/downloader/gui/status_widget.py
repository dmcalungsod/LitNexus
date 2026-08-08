import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QProgressBar, QLabel
)
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtCore import Qt, QObject, Signal

class ActivitySignalHandler(logging.Handler, QObject):
    new_record = Signal(dict)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord):
        # Convert record to a dict (safe for UI)
        data = {
            "timestamp": self.formatTime(record) if self.formatter else record.created,
            "level": record.levelname,
            "event": getattr(record, "event", "unknown"),
            "message": record.getMessage(),
            "operation_id": getattr(record, "operation_id", ""),
        }
        self.new_record.emit(data)

class StatusWidget(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Download / Cancel Buttons
        control_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel Download")
        self.cancel_btn.setStyleSheet("background-color: #D9534F; color: white;")
        self.cancel_btn.clicked.connect(self.controller.cancel_download)
        self.cancel_btn.hide()
        
        control_layout.addStretch()
        control_layout.addWidget(self.cancel_btn)
        layout.addLayout(control_layout)

        # Log Textbox
        self.log_textbox = QTextEdit()
        self.log_textbox.setReadOnly(True)
        self.log_textbox.setStyleSheet("font-family: monospace; font-size: 13px;")
        layout.addWidget(self.log_textbox)

        # Progress Bar removed (moved to WorkspaceWidget)

        # Utility Buttons
        util_layout = QHBoxLayout()
        self.retry_btn = QPushButton("Retry Failed")
        self.retry_btn.clicked.connect(self.controller.retry_failed_dois)
        
        self.view_failed_btn = QPushButton("View Failed")
        self.view_failed_btn.clicked.connect(self.controller.view_failed)
        
        self.open_output_btn = QPushButton("Open Output")
        self.open_output_btn.clicked.connect(self.controller.open_output_folder)
        
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)

        util_layout.addWidget(self.retry_btn)
        util_layout.addWidget(self.view_failed_btn)
        util_layout.addWidget(self.open_output_btn)
        util_layout.addWidget(self.clear_log_btn)
        layout.addLayout(util_layout)

    def append_record(self, data: dict):
        """Appends a structured log record to the textbox."""
        level = data.get("level", "")
        msg = data.get("message", "")
        event = data.get("event", "")
        
        color = "#CCCCCC"
        if level in ("ERROR", "CRITICAL"):
            color = "#D9534F"
        elif level == "WARNING":
            color = "#E69F00"
        elif "success" in msg.lower() or "completed" in msg.lower():
            color = "#2CC985"
        elif event in ("startup", "lifecycle"):
            color = "#56B4E9"
            
        timestamp = data.get("timestamp")
        if isinstance(timestamp, float):
            import datetime
            timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
        formatted_msg = f"[{timestamp}] {msg}"

        cursor = self.log_textbox.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_textbox.setTextCursor(cursor)
        
        self.log_textbox.insertHtml(f'<span style="color: {color};">{formatted_msg}</span><br>')
        self.log_textbox.moveCursor(QTextCursor.End)

    # set_progress moved to WorkspaceWidget

    def clear_log(self):
        self.log_textbox.clear()

    def set_locked(self, locked: bool):
        self.retry_btn.setEnabled(not locked)
        self.view_failed_btn.setEnabled(not locked)
        self.open_output_btn.setEnabled(not locked)
        self.clear_log_btn.setEnabled(not locked)
        self.cancel_btn.setVisible(locked)
