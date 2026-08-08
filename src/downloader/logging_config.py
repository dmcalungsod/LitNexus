import logging
import logging.handlers
import os
import sys
import threading
import atexit
from contextvars import ContextVar
from pathlib import Path

# ---- Correlation ID (operation_id) ----
_operation_id_var: ContextVar[str] = ContextVar("operation_id", default="")

def set_operation_id(op_id: str) -> None:
    _operation_id_var.set(op_id)

def get_operation_id() -> str:
    return _operation_id_var.get()

# ---- Custom filter to inject operation_id into every log record ----
class OperationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.operation_id = get_operation_id()
        if not hasattr(record, 'event'):
            record.event = 'none'
        return True

# ---- Global exception handler ----
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger = logging.getLogger("app")
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback), extra={"event": "crash"})

# ---- Logger initialisation ----
def setup_logging(level: int = logging.INFO, extra_handlers: list = None) -> None:
    """
    Call this once at application startup.
    Override log level with environment variable LITNEXUS_LOG_LEVEL
    """
    env_level = os.environ.get("LITNEXUS_LOG_LEVEL", "").upper()
    if env_level in logging._nameToLevel:
        level = logging._nameToLevel[env_level]

    # Determine log directory
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        else:
            base_dir = Path.home() / ".local" / "share"
        log_dir = base_dir / "LitNexus" / "logs"
    else:
        # Development mode: use the local logs folder in the project root
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10_485_760,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(event)s | %(message)s | op_id=%(operation_id)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    op_filter = OperationIdFilter()
    # We will add this to the queue_handler below instead of these handlers
    # so that the ContextVar is evaluated in the calling thread, not the listener thread.

    from logging.handlers import QueueHandler, QueueListener
    import queue

    log_queue = queue.Queue(-1)
    queue_handler = QueueHandler(log_queue)
    queue_handler.addFilter(op_filter)
    root_logger.addHandler(queue_handler)

    handlers = [file_handler, console_handler] + (extra_handlers or [])
    listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    listener.start()
    atexit.register(listener.stop)

    root_logger._queue_listener = listener

    sys.excepthook = handle_uncaught_exception
    threading.excepthook = lambda args: handle_uncaught_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    )

    logger = logging.getLogger("app")
    logger.info("application_started", extra={"event": "lifecycle"})
    logger.info(
        "diagnostics",
        extra={
            "event": "startup",
            "app_version": "1.0.0",
            "python_version": sys.version,
            "os": sys.platform,
            "database_path": str(Path.home() / "litnexus.db"),
            "log_path": str(log_file),
        }
    )

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def start_operation(op_id: str = None) -> str:
    if op_id is None:
        import uuid
        op_id = uuid.uuid4().hex[:8]
    set_operation_id(op_id)
    return op_id
