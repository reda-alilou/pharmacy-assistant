"""Connection infrastructure only; service tables belong to their own packages."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def create_database_engine(url: str):
    try:
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg":
            raise ValueError
    except Exception:
        raise ValueError("Database URL must use postgresql+psycopg.") from None
    return create_engine(parsed, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         hide_parameters=True,
                         connect_args={"connect_timeout": 5,
                                       "options": "-c statement_timeout=10000 -c lock_timeout=3000 -c timezone=UTC"})
