"""Start Qdrant via Docker Compose, run the API with uv, tear down on exit."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _compose(*args: str) -> int:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=BACKEND_ROOT,
        check=False,
    )
    return result.returncode


def _shutdown() -> None:
    logger.info("Stopping Docker Compose services...")
    _compose("down")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("Starting Qdrant (docker compose up -d)...")
    if _compose("up", "-d") != 0:
        sys.exit("docker compose up failed — is Docker running?")

    def handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %s", signum)
        _shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        from wagelens.server import main as run_server

        run_server()
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
