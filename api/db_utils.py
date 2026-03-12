"""Helper functions for database connectivity and metadata retrieval.

This module abstracts the bare minimum necessary to support the new
"Database Import/Export" feature described in the development spec.  Only
MSSQL and MariaDB/MySQL are supported initially; additional backends can be
added later.

We use SQLAlchemy for its unified URL syntax and lazy driver loading.  The
user is responsible for installing the appropriate DBAPI (pymysql for
MariaDB/MySQL, pymssql or pyodbc for SQL Server) and providing a valid
JDBC/ODBC driver path if required.
"""
from typing import Tuple, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


def _make_url(db_type: str, host: str, port: int, database: str,
              user: str, password: str, driver_path: Optional[str] = None) -> str:
    """Construct a SQLAlchemy URL for the given parameters.

    driver_path is currently ignored for MariaDB/MySQL but may be used for
    specifying an ODBC driver string for MSSQL.
    """
    if db_type.lower() in ('mssql', 'sqlserver'):
        # prefer pymssql if available; fall back to pyodbc with a driver
        try:
            import pymssql  # type: ignore
            return f"mssql+pymssql://{user}:{password}@{host}:{port}/{database}"
        except ImportError:
            # build pyodbc url; driver_path may contain the driver name
            drv = driver_path or "ODBC Driver 17 for SQL Server"
            # sqlalchemy expects the driver name percent-encoded
            drv_enc = drv.replace(' ', '+')
            return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}?driver={drv_enc}"
    elif db_type.lower() in ('mariadb', 'mysql'):
        # use pymysql driver
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def test_connection(db_type: str, host: str, port: int, database: str,
                    user: str, password: str, driver_path: Optional[str] = None) -> bool:
    """Attempt to connect to the database; return True if successful.

    Any exceptions are caught and returned as False.  Callers may inspect the
    exception message by wrapping this call themselves.
    """
    try:
        url = _make_url(db_type, host, port, database, user, password, driver_path)
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            # execute a lightweight statement
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_table_columns(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, table_name: str,
                      driver_path: Optional[str] = None) -> List[str]:
    """Return a list of column names for the given table.

    Raises SQLAlchemyError on failure.
    """
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    engine = create_engine(url)
    inspector = inspect(engine)
    cols = inspector.get_columns(table_name)
    return [c['name'] for c in cols]


def get_table_sample(db_type: str, host: str, port: int, database: str,
                     user: str, password: str, table_name: str,
                     driver_path: Optional[str] = None) -> Optional[dict]:
    """Return a single row (as dict) from the table, or None if empty.

    Useful for showing sample values next to column names.
    """
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    engine = create_engine(url)
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 1"))
            row = result.fetchone()
            if row is not None:
                return dict(row._mapping)
        except SQLAlchemyError:
            pass
    return None


def get_table_rows(db_type: str, host: str, port: int, database: str,
                   user: str, password: str, table_name: str,
                   driver_path: Optional[str] = None,
                   limit: Optional[int] = None) -> List[dict]:
    """Return all rows from the specified table as a list of dicts.

    The optional ``limit`` parameter can be used to restrict the number of
    rows returned (useful for previewing large tables).  SQLAlchemy is used
    for connection management; the caller is responsible for ensuring the
    table exists beforehand.
    """
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    engine = create_engine(url)
    with engine.connect() as conn:
        sql = f"SELECT * FROM {table_name}"
        if limit:
            sql += f" LIMIT {limit}"
        result = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchall()]
    return rows


def create_table_if_not_exists(db_type: str, host: str, port: int, database: str,
                               user: str, password: str, table_name: str,
                               columns: List[str],
                               driver_path: Optional[str] = None):
    """Create a simple table with given column names if it does not already exist.

    All columns are created with TEXT type for maximum compatibility.  This
    helper is intentionally minimal; callers can always create tables with a
    richer schema if desired.
    """
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    engine = create_engine(url)
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        cols_def = ", ".join(f"{col} TEXT" for col in columns)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE TABLE {table_name} ({cols_def})"))


def insert_rows(db_type: str, host: str, port: int, database: str,
                user: str, password: str, table_name: str,
                rows: List[dict],
                driver_path: Optional[str] = None):
    """Insert a list of rows (dicts) into the specified table.

    Each dict should map column names to values.  This helper performs a simple
    INSERT for each row; it does not attempt to deduplicate or perform updates.
    """
    if not rows:
        return
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    engine = create_engine(url)
    with engine.connect() as conn:
        for row in rows:
            cols = ", ".join(row.keys())
            params = ", ".join(f":{k}" for k in row.keys())
            conn.execute(text(f"INSERT INTO {table_name} ({cols}) VALUES ({params})"), **row)
