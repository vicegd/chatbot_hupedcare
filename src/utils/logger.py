import logging
from logging.handlers import RotatingFileHandler
import os
import yaml
from pathlib import Path

def setup_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Creates a logger based on a highly granular config.yaml.
    Supports dynamic levels, formats, and rotation settings.
    """
    
    # 1. Determine the Project Root (assuming this file is in 'src/')
    project_root = Path(__file__).resolve().parent.parent
    
    # 2. Load the configuration
    config_path = project_root / "config" / "config.yaml"
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        log_cfg = config.get("logger", {})
    except Exception:
        # Emergency defaults if YAML fails
        log_cfg = {}

    # 3. Extract settings with fallbacks
    log_folder = log_cfg.get("log_folder", "LOGS")
    console_level_name = log_cfg.get("log_console_level", "INFO")
    file_level_name = log_cfg.get("log_file_level", "DEBUG")
    console_log_format = log_cfg.get("log_console_format", "%(asctime)s - %(levelname)s - %(message)s")
    file_log_format = log_cfg.get("log_file_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    max_bytes = log_cfg.get("log_max_bytes", 5242880)  # Default 5MB
    backup_count = log_cfg.get("log_backup_count", 3)

    # 4. Map string levels to logging constants
    # This allows the YAML to use strings like "INFO"
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    console_level = level_map.get(console_level_name.upper(), logging.INFO)
    file_level = level_map.get(file_level_name.upper(), logging.DEBUG)

    # 5. Ensure the absolute log directory exists
    full_log_path = project_root / log_folder
    os.makedirs(full_log_path, exist_ok=True)

    # 6. Configure the Logger
    logger = logging.getLogger(logger_name)
    # The master level must be the lowest of both to let messages pass
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        file_formatter = logging.Formatter(file_log_format)
        console_formatter = logging.Formatter(console_log_format)

        # --- FILE HANDLER ---
        file_dest = full_log_path / log_filename
        file_handler = RotatingFileHandler(
            file_dest, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(file_level)

        # --- CONSOLE HANDLER ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_level)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger