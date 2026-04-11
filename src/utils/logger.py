import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Creates and configures a professional logger.
    Console: Shows INFO and above.
    File: Saves ALL levels (DEBUG and above).
    
    Args:
        logger_name (str): The internal name of the logger.
        log_filename (str): The name of the file (e.g., 'server.log').
        
    Returns:
        logging.Logger: The configured logger instance.
    """
    # 1. Ensure the 'logs' directory exists
    os.makedirs("logs", exist_ok=True)

    # 2. Create the specific logger
    logger = logging.getLogger(logger_name)
    
    # Set the main logger to the lowest level (DEBUG) 
    # so it allows all messages to pass through to the handlers
    logger.setLevel(logging.DEBUG)

    # 3. Check if handlers already exist to avoid duplicate logs
    if not logger.handlers:
        # Define the visual format of the log messages
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

        # --- FILE HANDLER ---
        # Purpose: Save everything (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_path = os.path.join("logs", log_filename)
        file_handler = RotatingFileHandler(file_path, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG) # Catch everything

        # --- CONSOLE HANDLER ---
        # Purpose: Show only relevant info (INFO, WARNING, ERROR, CRITICAL)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO) # Filter out DEBUG messages

        # Attach both handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger