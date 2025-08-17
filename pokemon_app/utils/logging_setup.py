"""Logging setup utility for the project.

Usage:
    from pokemon_app.utils.logging_setup import setup_logging
    setup_logging()
"""
from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path
import sys

def setup_logging(level: int = logging.INFO, log_to_file: bool = False, log_dir: str | None = None) -> None:
    logger = logging.getLogger()
    if logger.handlers:
        # Already configured
        return
    logger.setLevel(level)

    fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_to_file:
        path = Path(log_dir or (Path.cwd() / 'logs'))
        path.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(path / 'app.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        fh.setFormatter(fmt)
        logger.addHandler(fh)
