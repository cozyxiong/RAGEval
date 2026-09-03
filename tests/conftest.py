from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("EVAL_DB_PATH", "")


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "eval.db"
    os.environ["EVAL_DB_PATH"] = str(path)
    from api.config import settings

    settings.eval_db_path = str(path)
    from api import db as dbmod

    dbmod.reset_engine(str(path))
    dbmod.init_db()
    return path


@pytest.fixture()
def api_client(db_path: Path) -> Generator[TestClient, None, None]:
    from api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def mock_client() -> Generator[TestClient, None, None]:
    from adapters.mock_server import app as mock_app

    with TestClient(mock_app) as client:
        yield client


@pytest.fixture(scope="session")
def live_mock_url() -> Generator[str, None, None]:
    import uvicorn

    from adapters.mock_server import app as mock_app

    port = _free_port()
    config = uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 8
    import httpx

    while time.time() < deadline:
        if server.started:
            try:
                httpx.get(f"{url}/health", timeout=0.5).raise_for_status()
                break
            except Exception:
                pass
        time.sleep(0.05)
    else:
        raise RuntimeError("mock adapter failed to start")
    yield url
    server.should_exit = True
