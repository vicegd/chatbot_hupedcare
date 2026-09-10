"""
=============================================================================
RAG SYSTEM LOGGER
=============================================================================

This module acts as the "Black Box" flight recorder for the entire RAG system. 
Every time a file is downloaded, a database is updated, or the AI answers a 
question, this module safely records the event.

Why this is a robust, production-grade logger:
-----------------------------------------------------------------------------
1. AUTONOMOUS ROOT DETECTION: No matter where you launch your scripts from 
   (a cronjob, a sub-folder, or the root), it actively hunts for the project 
   root so the 'LOGS' folder is always created in the exact right place.
2. DUAL-STREAM OUTPUT: It maintains two different levels of verbosity. It prints 
   clean, simple 'INFO' to the terminal so you can watch it run, but it secretly 
   writes highly detailed 'DEBUG' data to a hidden file for troubleshooting.
3. SELF-CLEANING (ROTATION): Servers often crash when log files consume all 
   hard drive space. This uses a `RotatingFileHandler` that automatically 
   archives and deletes old logs once they reach a certain size (e.g., 5MB), 
   ensuring the server never runs out of space.
4. SAFE FALLBACKS: If the `config.yaml` is accidentally deleted or corrupted, 
   this logger won't crash. It has hardcoded emergency defaults to keep recording.
=============================================================================
"""

import logging
import os
from logging.handlers import RotatingFileHandler
import pathlib
import yaml

def get_project_root() -> pathlib.Path:
    """
    Find the repository root used to resolve configuration and log paths.

    Why we do this:
    Relative paths like '../config' break easily depending on how you execute 
    the Python script. This acts as a homing beacon, looking for the 'config' 
    folder to guarantee we always know where the absolute root of the project is.
    """
    # Start from the directory that contains this file.
    current_dir = pathlib.Path(__file__).resolve().parent
    
    # Check the current directory and the next three parents upward.
    for directory in [current_dir, current_dir.parent, current_dir.parent.parent, current_dir.parent.parent.parent]:
        # If a config directory or requirements file exists here, we found the root.
        if (directory / "config").is_dir() or (directory / "requirements.txt").exists():
            return directory
            
    # Fallback: assume the project root is one level above this file.
    return current_dir.parent

def setup_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Create or reuse a configured logger for the project.

    Args:
        logger_name: Logical logger name used by the Python logging subsystem.
        log_filename: Name of the log file written inside the configured log directory.

    Returns:
        A logger instance configured with rotating file and console handlers.
    """
    
    # ---------------------------------------------------------
    # 1 & 2. PATH RESOLUTION AND CONFIG LOADING
    # ---------------------------------------------------------
    project_root = get_project_root()
    config_path = project_root / "config" / "config.yaml"
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        log_cfg = config.get("logger", {})
    except Exception:
        # Safe fallback values if the YAML file is missing or invalid.
        # This prevents a logging failure from crashing the entire application.
        log_cfg = {}

    # ---------------------------------------------------------
    # 3. EXTRACT SETTINGS (With Bulletproof Defaults)
    # ---------------------------------------------------------
    log_folder = log_cfg.get("log_folder", "LOGS")
    console_level_name = log_cfg.get("log_console_level", "INFO")
    file_level_name = log_cfg.get("log_file_level", "DEBUG")
    console_format = log_cfg.get("log_console_format", "%(asctime)s - %(levelname)s - %(message)s")
    file_format = log_cfg.get("log_file_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Force integer values to avoid type-crashes if someone accidentally 
    # writes strings like "5MB" instead of numbers in the YAML file.
    try:
        max_bytes = int(log_cfg.get("log_max_bytes", 5242880)) # Default 5MB
        backup_count = int(log_cfg.get("log_backup_count", 3)) # Keep 3 backups
    except (ValueError, TypeError):
        max_bytes = 5242880
        backup_count = 3

    # ---------------------------------------------------------
    # 4. MAP STRING NAMES TO LOGGING CONSTANTS
    # ---------------------------------------------------------
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    console_level = level_map.get(str(console_level_name).upper(), logging.INFO)
    file_level = level_map.get(str(file_level_name).upper(), logging.DEBUG)

    # ---------------------------------------------------------
    # 5. DIRECTORY CREATION
    # ---------------------------------------------------------
    # Ensure the physical folder exists at the absolute project root
    full_log_path = project_root / log_folder
    os.makedirs(full_log_path, exist_ok=True)

    # ---------------------------------------------------------
    # 6. CORE LOGGER CONFIGURATION
    # ---------------------------------------------------------
    logger = logging.getLogger(logger_name)
    
    # Important: The master logger must be set to the lowest possible level (DEBUG).
    # If the master is set to INFO, the File Handler will never receive DEBUG messages,
    # even if the File Handler itself is set to DEBUG.
    logger.setLevel(logging.DEBUG) 

    # Avoid adding multiple duplicate handlers if 'setup_logger' is called 
    # more than once by different files during the same session.
    if not logger.handlers:
        
        # Split formatter setup so console and file output can look different
        file_formatter = logging.Formatter(file_format)
        console_formatter = logging.Formatter(console_format)

        # --- FILE HANDLER: Persists logs to the hard drive ---
        file_dest = full_log_path / log_filename
        file_handler = RotatingFileHandler(
            file_dest, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(file_level)

        # --- CONSOLE HANDLER: Prints logs to the terminal screen ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_level)

        # Attach the configured handlers to the master logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger