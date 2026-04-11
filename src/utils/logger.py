import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(logger_name: str, log_filename: str, level=logging.INFO) -> logging.Logger:
    """
    Creates and configures a professional logger with file rotation and console output.
    
    Args:
        logger_name (str): The internal name of the logger.
        log_filename (str): The name of the file (e.g., 'server.log').
        level: The minimum logging level to record (default is INFO).
        
    Returns:
        logging.Logger: The configured logger instance.
    """
    # 1. Ensure the 'logs' directory exists at the root of the project
    os.makedirs("logs", exist_ok=True)

    # 2. Create the specific logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # 3. Check if handlers already exist to avoid duplicate logs in the console/file
    if not logger.handlers:
        # Define the visual format of the log messages
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

        # Create the File Handler (Max 5MB per file, keep up to 3 old backups)
        file_path = os.path.join("logs", log_filename)
        file_handler = RotatingFileHandler(file_path, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setFormatter(formatter)

        # Create the Console Handler (Prints to the terminal)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Attach the handlers to our logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger