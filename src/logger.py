import os
import logging
from logging.handlers import RotatingFileHandler
from src.config import load_config, project_path

def setup_logger():
    max_bytes = 1048576 # 1MB default
    backup_count = 10
    
    config = load_config()
    max_bytes = config.get("log_max_bytes", max_bytes)
    backup_count = config.get("log_backup_count", backup_count)
            
    logs_dir = project_path("logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "app.log")
    
    logger = logging.getLogger("rag_poc")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # File handler
        file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
