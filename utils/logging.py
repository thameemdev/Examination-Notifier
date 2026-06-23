import logging
import os
from logging.handlers import RotatingFileHandler
from utils.config import Config

def setup_logger(name: str, log_file: str, level=logging.INFO) -> logging.Logger:
    """Sets up a logger with a rotating file handler and standard console output."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # Ensure log directory exists
    log_path = os.path.join(Config.LOG_DIR, log_file)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if logger is already set up
    if not logger.handlers:
        # Rotating File Handler (Max 5MB per file, backup count of 5)
        file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

# Get log level from config
numeric_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

# Setup specialized loggers
scheduler_logger = setup_logger("scheduler", "scheduler.log", numeric_level)
notifications_logger = setup_logger("notifications", "notifications.log", numeric_level)
error_logger = setup_logger("errors", "errors.log", logging.ERROR)

def get_logger(module_name: str) -> logging.Logger:
    """Helper function to return a logger for a specific module, logging to main app log."""
    logger = setup_logger(module_name, "app.log", numeric_level)
    
    # Ensure error logger also gets error level messages from this logger
    # by adding the error handler or just using standard app routing.
    # To keep log files separate:
    err_log_path = os.path.join(Config.LOG_DIR, "errors.log")
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename.endswith("errors.log") for h in logger.handlers):
        err_handler = RotatingFileHandler(err_log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(err_handler)
        
    return logger
