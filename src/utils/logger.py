import logging
from logging.handlers import RotatingFileHandler
import os
import yaml
from pathlib import Path

def get_project_root() -> Path:
    """
    Find the repository root used to resolve configuration and log paths.

    Returns:
        A `Path` pointing to the first parent directory that contains either
        `config/` or `requirements.txt`.
    """
    # Start from the directory that contains this file.
    current_dir = Path(__file__).resolve().parent
    
    # Check the current directory and the next three parents.
    for directory in [current_dir, current_dir.parent, current_dir.parent.parent, current_dir.parent.parent.parent]:
        # If a config directory or requirements file exists here, this is the root.
        if (directory / "config").is_dir() or (directory / "requirements.txt").exists():
            return directory
            
    # Fallback: assume the project root is one level above this file.
    return current_dir.parent

def setup_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Create or reuse a configured logger for the project.

    Args:
        logger_name: Logical logger name used by the Python logging subsystem.
        log_filename: Name of the log file written inside the configured log
            directory.

    Returns:
        A logger instance configured with rotating file and console handlers.
    """
    
    # 1. Resolve the actual project root.
    project_root = get_project_root()
    
    # 2. Load the configuration from the project root.
    config_path = project_root / "config" / "config.yaml"
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        log_cfg = config.get("logger", {})
    except Exception:
        # Safe fallback values if the YAML file is missing or invalid.
        log_cfg = {}

    # 3. Extract configuration with safe defaults.
    # These defaults keep logging operational even if config.yaml is incomplete.
    log_folder = log_cfg.get("log_folder", "LOGS")
    console_level_name = log_cfg.get("log_console_level", "INFO")
    file_level_name = log_cfg.get("log_file_level", "DEBUG")
    console_format = log_cfg.get("log_console_format", "%(asctime)s - %(levelname)s - %(message)s")
    file_format = log_cfg.get("log_file_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Force integer values to avoid type issues from misconfigured YAML entries.
    try:
        max_bytes = int(log_cfg.get("log_max_bytes", 5242880))
        backup_count = int(log_cfg.get("log_backup_count", 3))
    except (ValueError, TypeError):
        max_bytes = 5242880
        backup_count = 3

    # 4. Map YAML level names to logging constants.
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    console_level = level_map.get(str(console_level_name).upper(), logging.INFO)
    file_level = level_map.get(str(file_level_name).upper(), logging.DEBUG)

    # 5. Create the log directory at the project root.
    full_log_path = project_root / log_folder
    os.makedirs(full_log_path, exist_ok=True)

    # 6. Configure the core logger.
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Keep the master level at DEBUG so all records pass through.

    # Avoid duplicate handlers if setup_logger is called multiple times.
    if not logger.handlers:
        # Split formatter setup from handler setup so console and file output can diverge cleanly.
        file_formatter = logging.Formatter(file_format)
        console_formatter = logging.Formatter(console_format)

        # --- File handler: persists logs under the configured log directory. ---
        file_dest = full_log_path / log_filename
        file_handler = RotatingFileHandler(
            file_dest, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(file_level)

        # --- Console handler: prints logs to the active terminal. ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_level)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger