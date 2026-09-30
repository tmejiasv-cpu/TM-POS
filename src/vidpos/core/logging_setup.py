"""Configuración de logging de vidPOS."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime

from vidpos.config import LOGS_DIR

_CONFIGURED = False


def setup_logging(level: int = logging.INFO, console: bool = True) -> None:
    """Configura logging a archivo con rotación + consola opcional.

    Se puede llamar varias veces sin duplicar handlers.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    fmt_file = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fmt_console = logging.Formatter("%(levelname)s: %(message)s")

    log_file = LOGS_DIR / f"vidpos_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt_file)
    root.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(fmt_console)
        root.addHandler(console_handler)

    # Silenciar ruido de librerías externas
    logging.getLogger("PIL").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.info("Logging configurado. Nivel: %s", logging.getLevelName(level))