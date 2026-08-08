import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import setup_logging  # noqa: E402


def verify_gui_logging():
    # Define log path as in run.py
    if getattr(sys, "frozen", False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = str(Path(__file__).parent.parent)

    log_dir = os.path.join(application_path, "logs")
    log_file_path = os.path.join(log_dir, "litnexus.log")
    log_file = Path(log_file_path)

    print(f"Log file path: {log_file}")

    # Clear existing logs
    if log_file.exists():
        log_file.unlink()
    for i in range(1, 4):
        backup = log_file.with_name(f"{log_file.name}.{i}")
        if backup.exists():
            backup.unlink()

    # Force clear handlers
    logging.root.handlers = []

    # Setup logging
    setup_logging()

    # Verify handler configuration
    root_logger = logging.getLogger()
    file_handlers = [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]

    if not file_handlers:
        print("Error: No RotatingFileHandler found attached to root logger.")
        return

    handler = file_handlers[0]
    print(f"Handler maxBytes: {handler.maxBytes}")
    print(f"Handler backupCount: {handler.backupCount}")

    if handler.maxBytes != 5 * 1024 * 1024:
        print("Error: maxBytes is not 5MB.")
    if handler.backupCount != 2:
        print("Error: backupCount is not 2.")

    # Write logs to trigger rotation
    logger = logging.getLogger("test_gui_logger")
    # run.py sets root level to DEBUG, so this should work

    print("Writing logs...")
    chunk = "x" * 1024 * 1024  # 1MB
    # Write 12MB to trigger rotation (5MB limit * 2 + 2MB)
    for i in range(12):
        logger.info(f"Chunk {i}")
        logger.info(chunk)
        print(f"Written chunk {i+1}/12")

    # Check files
    files = [log_file] + [log_file.with_name(f"{log_file.name}.{i}") for i in range(1, 4)]
    found = []
    for f in files:
        if f.exists():
            size = f.stat().st_size
            print(f"Found {f.name}: {size / 1024 / 1024:.2f} MB")
            found.append(f)
        else:
            print(f"Missing {f.name}")

    # Check for timestamp
    if log_file.exists():
        content = log_file.read_text(encoding="utf-8")
        print("\nFirst 100 chars of latest log:")
        print(content[:100])

        # Format: "%(asctime)s [%(levelname)-8s] [%(name)-25s] %(message)s"
        # Example: 2023-10-27 10:00:00 [INFO    ] [test_gui_logger          ] Chunk ...
        if " [INFO    ] [test_gui_logger          ] Chunk" in content:
            print("\nTimestamp verification passed (format check).")
        else:
            print("\nTimestamp verification failed or content mismatch.")

    # We expect app.log, app.log.1, app.log.2 (3 files total)
    # app.log.3 should NOT exist if backupCount is 2
    if len(found) == 3:
        print("\nRotation verification passed (exactly 3 files found).")
    elif len(found) > 3:
        print(f"\nRotation verification failed (too many files: {len(found)}).")
    else:
        print(f"\nRotation verification failed (too few files: {len(found)}).")


if __name__ == "__main__":
    verify_gui_logging()
