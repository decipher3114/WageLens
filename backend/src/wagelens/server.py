"""Uvicorn entrypoint — uvicorn logs to console, app logs to file."""

import uvicorn

from wagelens.config import settings
from wagelens.logging_config import get_uvicorn_log_config


def main() -> None:
    uvicorn.run(
        "wagelens.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        log_config=get_uvicorn_log_config(level=settings.log_level),
    )


if __name__ == "__main__":
    main()
