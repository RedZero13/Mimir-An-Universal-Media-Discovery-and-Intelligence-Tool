import os
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL", "postgresql://postgres:postgres@localhost:5432/postgres")


def _db_available() -> bool:
    try:
        psycopg.connect(ADMIN_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


@pytest.fixture(scope="session")
def database_url():
    """A throwaway database per test session, migrated and seeded."""
    if not _db_available():
        pytest.skip("PostgreSQL not available (set TEST_DATABASE_ADMIN_URL)")
    name = f"mde_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    url = ADMIN_URL.rsplit("/", 1)[0] + "/" + name
    from mde.catalogue.load import load_seed
    from mde.migrate import migrate
    with psycopg.connect(url, row_factory=dict_row) as conn:
        migrate(conn)
        load_seed(conn)
    yield url
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def conn(database_url):
    with psycopg.connect(database_url, row_factory=dict_row) as c:
        yield c
        c.rollback()
