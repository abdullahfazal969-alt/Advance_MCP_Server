import logging
import os
from pathlib import Path
from research_assistance.core.config import PROJECT_ROOT, LOG_LEVEL # Import LOG_LEVEL from config

def setup_logging():
    """
    Configures logging for the FastMCP server, directing output to a file
    and optionally to the console.
    """
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True) # Ensure logs directory exists
    log_file = log_dir / "server.log"

    # Get the root logger
    # Setting level to DEBUG to ensure all messages are captured by handlers
    # Handlers will then filter based on their own level.
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) 

    # Clear existing handlers to prevent duplicate logs in case of re-init
    # This is important if setup_logging() might be called multiple times
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # File handler: writes logs to a file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(LOG_LEVEL) # Use LOG_LEVEL from config
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler: writes logs to stderr (visible in terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL) # Use LOG_LEVEL from config
    console_formatter = logging.Formatter(
        "%(levelname)s: %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Optionally, configure specific loggers for FastMCP or other libraries
    # to control verbosity from external components.
    # For example, to make FastMCP less verbose by default:
    logging.getLogger("fastmcp").setLevel(logging.INFO) 
    
    logger.info("Logging configured successfully.")
