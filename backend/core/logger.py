import logging
import sys
from contextvars import ContextVar
from typing import Optional

# --- 1. Session Context (The Magic Variable) ---
# This ContextVar works like a "Thread-Local" variable but for Asyncio.
# It holds the 'session_id' specific to the current request context.
# Default is 'System' (for startup logs or background tasks).
session_context: ContextVar[str] = ContextVar("session_id", default="System")

class SessionFilter(logging.Filter):
    """
    A Logging Filter that injects the current 'session_id' 
    from the ContextVar into every log record.
    """
    def filter(self, record):
        # This makes 'record.session_id' available for the Formatter
        record.session_id = session_context.get()
        return True

class ColoredFormatter(logging.Formatter):
    """
    Custom Formatter to add colors to the console output 
    based on the log level.
    """
    # ANSI Escape Codes for Colors
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    # Log Format: [Time] [Level] [SessionID] Message
    # Example: [10:05:21] [INFO] [sess-123] Transcriber initialized.
    fmt_str = "[%(asctime)s] [%(levelname)s] [%(session_id)s] %(message)s"

    FORMATS = {
        logging.DEBUG: grey + fmt_str + reset,
        logging.INFO: green + fmt_str + reset,
        logging.WARNING: yellow + fmt_str + reset,
        logging.ERROR: red + fmt_str + reset,
        logging.CRITICAL: bold_red + fmt_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

def setup_logger():
    """
    Configures and returns the application logger.
    """
    # Create a named logger (avoid using root logger to prevent library conflicts)
    logger = logging.getLogger("clinical_backend")
    logger.setLevel(logging.INFO)
    
    # Prevent adding multiple handlers if setup is called multiple times
    if not logger.handlers:
        # 1. Stream Handler (Console)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter())
        console_handler.addFilter(SessionFilter()) # 👈 Inject Session ID
        
        logger.addHandler(console_handler)
        
        # 2. File Handler (Optional: For persistent logs)
        # file_handler = logging.FileHandler("app_system.log")
        # file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(session_id)s] %(message)s")
        # file_handler.setFormatter(file_formatter)
        # file_handler.addFilter(SessionFilter())
        # logger.addHandler(file_handler)

    return logger

# --- Singleton Export ---
# Use this 'logger' throughout the app.
# Use 'session_context' in middleware to set the session ID.
logger = setup_logger()