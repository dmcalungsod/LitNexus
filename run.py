import os
import sys

# --- Original code to add 'src' to path ---
if not getattr(sys, "frozen", False):
    src_path = os.path.join(os.path.dirname(__file__), "src")
    sys.path.insert(0, os.path.abspath(src_path))

if __name__ == "__main__":
    from src.downloader.logging_config import setup_logging, get_logger
    from src.downloader.gui.status_widget import ActivitySignalHandler

    activity_handler = ActivitySignalHandler()
    setup_logging(extra_handlers=[activity_handler])

    logger = get_logger("app")
    logger.info("Application starting...", extra={"event": "startup"})

    try:
        from src.downloader.gui.__main__ import main
        main(activity_handler=activity_handler)
    except Exception:
        logger.exception("Fatal error during application startup", extra={"event": "crash"})
        raise
    logger.info("Application closed.", extra={"event": "shutdown"})
