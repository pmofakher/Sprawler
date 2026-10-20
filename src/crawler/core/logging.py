"""Structured logging system with console and rotating file support."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class ContextFilter(logging.Filter):
    """Injects contextual attributes into log records."""

    def __init__(self, job_id: str = "-", domain: str = "-", url: str = "-"):
        super().__init__()
        self.job_id = job_id
        self.domain = domain
        self.url = url

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = self.job_id
        if not hasattr(record, "domain"):
            record.domain = self.domain
        if not hasattr(record, "url"):
            record.url = self.url
        return True


def setup_logger(
    name: str = "sprawler",
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    job_id: str = "-",
    domain: str = "-",
) -> logging.Logger:
    """Configures and returns a logger instance with console and optional rotating file output."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] [job:%(job_id)s] [domain:%(domain)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Set context filter
    context_filter = ContextFilter(job_id=job_id, domain=domain)
    logger.addFilter(context_filter)

    # Attach file handler if log file path provided
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=10 * 1024 * 1024,  # 10 MB per log file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] [job:%(job_id)s] [domain:%(domain)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(context_filter)
        logger.addHandler(file_handler)

    return logger


# Global root logger
logger = setup_logger("sprawler")
