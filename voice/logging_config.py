"""
Voice Ledger Logging Configuration

Centralized logging setup for all Voice Ledger modules.
Configures console and file logging with proper formatting and levels.

Usage:
    from voice.logging_config import setup_logging
    setup_logging()
"""

import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Project root for log files
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

def setup_logging(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    enable_file_logging: bool = True,
    max_file_size_mb: int = 50,
    backup_count: int = 5
):
    """
    Configure logging for all Voice Ledger modules.
    
    Args:
        console_level: Logging level for console output (DEBUG, INFO, WARNING, ERROR)
        file_level: Logging level for file output
        enable_file_logging: Whether to write logs to files
        max_file_size_mb: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    
    # Create formatters
    console_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_handler.setFormatter(console_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything
    root_logger.handlers.clear()  # Remove existing handlers
    root_logger.addHandler(console_handler)
    
    # File handlers (if enabled)
    if enable_file_logging:
        # Main application log
        main_log_file = LOGS_DIR / "voice_ledger.log"
        main_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        main_handler.setLevel(getattr(logging, file_level.upper()))
        main_handler.setFormatter(file_formatter)
        root_logger.addHandler(main_handler)
        
        # Error-specific log
        error_log_file = LOGS_DIR / "errors.log"
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # Module-specific logs
        module_logs = {
            'voice.asr': LOGS_DIR / "asr.log",
            'voice.rag': LOGS_DIR / "rag.log", 
            'voice.cache': LOGS_DIR / "cache.log",
            'voice.tasks': LOGS_DIR / "celery.log",
            'voice.telegram': LOGS_DIR / "telegram.log",
            'voice.verification': LOGS_DIR / "verification.log",
            'voice.nlu': LOGS_DIR / "nlu.log",
            'voice.integrations': LOGS_DIR / "integrations.log"
        }
        
        for module_name, log_file in module_logs.items():
            module_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            module_handler.setLevel(getattr(logging, file_level.upper()))
            module_handler.setFormatter(file_formatter)
            
            # Get module logger and add handler
            module_logger = logging.getLogger(module_name)
            module_logger.addHandler(module_handler)
            module_logger.setLevel(logging.DEBUG)
    
    # Configure specific library loggers
    library_loggers = {
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
        'openai': logging.INFO,
        'celery': logging.INFO,
        'redis': logging.WARNING,
        'sqlalchemy': logging.WARNING,
        'httpx': logging.WARNING,
        'transformers': logging.WARNING,
        'torch': logging.WARNING,
        'web3': logging.WARNING
    }
    
    for lib_name, level in library_loggers.items():
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(level)
    
    # Log that logging has been configured
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Voice Ledger Logging System Initialized")
    logger.info(f"Console Level: {console_level}")
    logger.info(f"File Level: {file_level}")
    logger.info(f"File Logging: {'Enabled' if enable_file_logging else 'Disabled'}")
    if enable_file_logging:
        logger.info(f"Log Directory: {LOGS_DIR}")
        logger.info("Module-specific logs: asr.log, rag.log, cache.log, celery.log, telegram.log, verification.log, nlu.log, integrations.log")
    logger.info("=" * 60)

def get_logger(name: str) -> logging.Logger:
    """
    Get a properly configured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

def log_system_info():
    """Log system information for debugging."""
    logger = logging.getLogger(__name__)
    logger.info("System Information:")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Working Directory: {os.getcwd()}")
    logger.info(f"Project Root: {PROJECT_ROOT}")
    logger.info(f"Log Directory: {LOGS_DIR}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")

# Auto-setup when imported
setup_logging()
