"""Central logging configuration for the WageLens backend."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

from uvicorn.logging import AccessFormatter, DefaultFormatter

LogFormat = Literal["text", "json"]

_TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_APP_LOGGER = "wagelens"

_CONFIGURED = False


class _BackendLogFilter(logging.Filter):
    """Ensure only application loggers are written to the log file."""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        return name == _APP_LOGGER or name.startswith(f"{_APP_LOGGER}.")


def _build_formatter(log_format: LogFormat) -> logging.Formatter:
    if log_format == "json":
        return _JsonFormatter()
    return logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT)


def _configure_uvicorn_console(level: int) -> None:
    """Send uvicorn server/access logs to the terminal only."""
    server_formatter = DefaultFormatter(
        fmt="%(levelprefix)s %(message)s",
        use_colors=sys.stderr.isatty(),
    )
    access_formatter = AccessFormatter(
        fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        use_colors=sys.stdout.isatty(),
    )

    server_handler = logging.StreamHandler(sys.stderr)
    server_handler.setLevel(level)
    server_handler.setFormatter(server_formatter)

    access_handler = logging.StreamHandler(sys.stdout)
    access_handler.setLevel(level)
    access_handler.setFormatter(access_formatter)

    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.setLevel(level)
        uvicorn_logger.propagate = False
        uvicorn_logger.handlers.clear()
        uvicorn_logger.addHandler(server_handler)

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(level)
    access_logger.propagate = False
    access_logger.handlers.clear()
    access_logger.addHandler(access_handler)


def setup_logging(
    *,
    level: str = "INFO",
    log_format: LogFormat = "text",
    log_file: str = "./data/logs/wagelens.log",
) -> Path:
    """Route wagelens.* loggers to a rotating file; uvicorn logs to console."""
    global _CONFIGURED
    if _CONFIGURED:
        return Path(log_file)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = _build_formatter(log_format)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_BackendLogFilter())

    app_logger = logging.getLogger(_APP_LOGGER)
    app_logger.setLevel(numeric_level)
    app_logger.propagate = False
    app_logger.handlers.clear()
    app_logger.addHandler(file_handler)

    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.handlers.clear()

    _configure_uvicorn_console(numeric_level)

    for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    app_logger.info(
        "Application logging configured: level=%s format=%s file=%s",
        level.upper(),
        log_format,
        log_path.resolve(),
    )
    return log_path


def get_uvicorn_log_config(*, level: str = "INFO") -> dict:
    """Uvicorn log config dict — console only, does not touch wagelens loggers."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "use_colors": True,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            },
            "access_console": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access_console"],
                "level": level.upper(),
                "propagate": False,
            },
            _APP_LOGGER: {
                "handlers": [],
                "level": level.upper(),
                "propagate": False,
            },
        },
        "root": {"level": "WARNING", "handlers": []},
    }


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log lines for production log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload = {
            "timestamp": self.formatTime(record, _DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def truncate(text: str, max_len: int = 120) -> str:
    """Shorten long strings for safe log output."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3]}..."
