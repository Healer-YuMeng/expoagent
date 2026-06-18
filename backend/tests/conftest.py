import sys
import asyncio
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import connect_to_postgres, close_postgres_connection


@pytest.fixture(scope="session", autouse=True)
def postgres_connection():
    asyncio.run(connect_to_postgres())
    yield
    asyncio.run(close_postgres_connection())
