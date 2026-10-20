"""Connection infrastructure only; service tables belong to their own packages."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def validate_database_url(url: str) -> str:
    try:
        parsed = make_url(url)
        if (parsed.drivername != "postgresql+psycopg" or not parsed.host
                or not parsed.username or not parsed.database):
            raise ValueError
    except Exception:
        raise ValueError("Database URL must use postgresql+psycopg and include a host, user and database.") from None
    return url


def create_database_engine(url: str):
    parsed = make_url(validate_database_url(url))
    return create_engine(parsed, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         hide_parameters=True,
                         connect_args={"connect_timeout": 5,
                                       "options": "-c statement_timeout=10000 -c lock_timeout=3000 -c timezone=UTC"})
