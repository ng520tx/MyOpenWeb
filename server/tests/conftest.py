"""Test bootstrap: sandbox the SQLite data dir before any server import."""
from __future__ import annotations

import os
import tempfile

# server.db resolves DATA_DIR at import time, so this must run first.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="myopenweb-test-")
os.environ["MYOPENWEB_DATA_DIR"] = _TEST_DATA_DIR

import pytest  # noqa: E402

from server.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    init_db()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
