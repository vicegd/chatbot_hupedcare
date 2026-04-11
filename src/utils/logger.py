import logging
from logging.handlers import RotatingFileHandler
import os
import yaml
from pathlib import Path

def get_project_root() -> Path:
    """
    Busca de forma inteligente la raíz del proyecto.
    Rastrea hacia arriba hasta encontrar la carpeta 'config' o el 'requirements.txt'.
    """
    # Empezamos en la carpeta donde está guardado ESTE archivo (logger.py)
    current_dir = Path(__file__).resolve().parent
    
    # Revisamos la carpeta actual y las 3 superiores por si acaso
    for directory in [current_dir, current_dir.parent, current_dir.parent.parent, current_dir.parent.parent.parent]:
        # Si vemos que aquí existe una carpeta llamada 'config', ¡esta es la raíz!
        if (directory / "config").is_dir() or (directory / "requirements.txt").exists():
            return directory
            
    # Plan de emergencia: si no encuentra nada, asume que la raíz está un nivel por encima de este archivo
    return current_dir.parent

def setup_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Crea un logger profesional. Configuración autónoma y detección de raíz absoluta.
    """
    
    # 1. Determinamos la raíz real del proyecto de forma blindada
    project_root = get_project_root()
    
    # 2. Cargamos la configuración desde la raíz
    config_path = project_root / "config" / "config.yaml"
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        log_cfg = config.get("logger", {})
    except Exception:
        # Valores de emergencia si el YAML no existe o falla
        log_cfg = {}

    # 3. Extraemos la configuración (con valores por defecto seguros)
    log_folder = log_cfg.get("log_folder", "LOGS")
    console_level_name = log_cfg.get("log_console_level", "INFO")
    file_level_name = log_cfg.get("log_file_level", "DEBUG")
    console_format = log_cfg.get("log_console_format", "%(asctime)s - %(levelname)s - %(message)s")
    file_format = log_cfg.get("log_file_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Forzamos que sean números enteros para evitar errores si en el YAML hay texto
    try:
        max_bytes = int(log_cfg.get("log_max_bytes", 5242880))
        backup_count = int(log_cfg.get("log_backup_count", 3))
    except (ValueError, TypeError):
        max_bytes = 5242880
        backup_count = 3

    # 4. Mapeamos los textos del YAML a las constantes reales de logging
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    console_level = level_map.get(str(console_level_name).upper(), logging.INFO)
    file_level = level_map.get(str(file_level_name).upper(), logging.DEBUG)

    # 5. CREACIÓN DE LA CARPETA (Garantizado en la raíz)
    full_log_path = project_root / log_folder
    os.makedirs(full_log_path, exist_ok=True)

    # 6. Configuración Core del Logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Nivel maestro siempre en DEBUG para que pase todo

    # Evitamos duplicar mensajes si la función se llama varias veces
    if not logger.handlers:
        file_formatter = logging.Formatter(file_format)
        console_formatter = logging.Formatter(console_format)

        # --- FILE HANDLER (El que guarda en la carpeta LOGS) ---
        file_dest = full_log_path / log_filename
        file_handler = RotatingFileHandler(
            file_dest, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(file_level)

        # --- CONSOLE HANDLER (El que imprime en la pantalla) ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_level)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger