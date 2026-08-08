import sys
from PySide6.QtWidgets import QApplication
from src.downloader.gui.main_window import MainWindow

def main(activity_handler=None):
    app = QApplication(sys.argv)
    window = MainWindow()
    if activity_handler:
        activity_handler.new_record.connect(window.status_widget.append_record)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
