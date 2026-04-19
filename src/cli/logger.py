"""Logging configuration for NarrativeForge CLI."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class NarrativeLogger:
    """Logger robusto para CLI."""

    def __init__(self, name: str = "narrative", log_dir: Optional[Path] = None):
        self.name = name
        self.log_dir = log_dir or Path("logs")
        self._logger: Optional[logging.Logger] = None
        self._error_logger: Optional[logging.Logger] = None
        self._setup_loggers()

    def _setup_loggers(self) -> None:
        """Configura los loggers."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        main_log = self.log_dir / f"narrative-{today}.log"
        error_log = self.log_dir / f"narrative-error-{today}.log"

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(main_log, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # Root logger: recibe todos los loggers del proyecto (src.*, httpx, etc.)
        # Solo escribe al archivo para no contaminar la consola.
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        # Evitar handlers duplicados si _setup_loggers se llama más de una vez
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(main_log.resolve())
                   for h in root_logger.handlers):
            root_logger.addHandler(file_handler)

        # "narrative" logger: mensajes de CLI/orquestador con formato idéntico.
        # propagate=False evita que sus mensajes lleguen también al root (doble escritura).
        self._logger = logging.getLogger(self.name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()
        self._logger.propagate = False
        self._logger.addHandler(file_handler)

        # Consola: solo WARNING+ para no ensuciar la salida del usuario
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        self._error_logger = logging.getLogger(f"{self.name}-error")
        self._error_logger.setLevel(logging.ERROR)
        self._error_logger.handlers.clear()
        self._error_logger.propagate = False

        error_handler = logging.FileHandler(error_log, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self._error_logger.addHandler(error_handler)

    def debug(self, message: str, module: str = "", line: int = 0) -> None:
        """Log debug message."""
        self._logger.debug(message)

    def info(self, message: str, module: str = "", line: int = 0) -> None:
        """Log info message."""
        self._logger.info(message)

    def warning(self, message: str, module: str = "", line: int = 0) -> None:
        """Log warning message."""
        self._logger.warning(message)

    def error(self, message: str, module: str = "", line: int = 0) -> None:
        """Log error message (both to file and error file)."""
        self._logger.error(message)
        self._error_logger.error(message)

    def critical(self, message: str, module: str = "", line: int = 0) -> None:
        """Log critical message."""
        self._logger.critical(message)
        self._error_logger.critical(message)


logger = NarrativeLogger()
