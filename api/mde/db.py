"""Database access. One connection per request/job; the catalogue is small enough not to need a pool yet."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/mde"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


@contextmanager
def connect(url: str | None = None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(url or database_url(), row_factory=dict_row) as conn:
        yield conn
