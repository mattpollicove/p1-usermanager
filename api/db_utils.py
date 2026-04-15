"""Helper functions for database connectivity and metadata retrieval.

This module abstracts the bare minimum necessary to support the new
"Database Import/Export" feature described in the development spec.  Only
MSSQL and MariaDB/MySQL are supported initially; additional backends can be
added later.

We use SQLAlchemy for its unified URL syntax and lazy driver loading.  The
user is responsible for installing the appropriate DBAPI (pymysql for
MariaDB/MySQL, pymssql or pyodbc for SQL Server) and, for ODBC
connections, specifying a driver name or path.  The connection dialog now
offers a dropdown of common driver names.
"""
from typing import Tuple, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


def _quote_identifier(db_type: str, ident: str) -> str:
    """Return a safely quoted SQL identifier for the target database type.

    This treats ``ident`` as a single identifier token. It is suitable for
    column names, including legacy names that may themselves contain dots.
    """
    db_lower = (db_type or "").lower()
    token = str(ident or "")
    if not token:
        raise ValueError("Identifier cannot be empty")

    if db_lower in ('mssql', 'sqlserver') or 'mssql' in db_lower:
        return f"[{token.replace(']', ']]')}]"
    # MariaDB/MySQL default
    return f"`{token.replace('`', '``')}`"


def _quote_table_identifier(db_type: str, ident: str) -> str:
    """Return a quoted table identifier, supporting dotted schema.table paths.
    
    Strips whitespace from identifiers to prevent SQL errors.
    """
    ident = str(ident or "").strip()
    parts = [p.strip() for p in ident.split('.') if p.strip()]
    if not parts:
        raise ValueError("Identifier cannot be empty")
    return '.'.join(_quote_identifier(db_type, p) for p in parts)


def _make_url(db_type: str, host: str, port: int, database: str,
              user: str, password: str, driver_path: Optional[str] = None) -> str:
    """Construct a SQLAlchemy URL for the given parameters.

    Accepts database type as either the combo box display name ("MariaDB/MySQL",
    "MSSQL") or the shorthand ("mariadb", "mysql", "mssql", "sqlserver").
    driver_path is currently ignored for MariaDB/MySQL but may be used for
    specifying an ODBC driver string (name or path) for MSSQL.
    """
    # Validate database name is provided
    if not database or not str(database).strip():
        raise ValueError("Database name cannot be empty")
    
    db_lower = db_type.lower()
    if db_lower in ('mssql', 'sqlserver') or 'mssql' in db_lower:
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
    elif db_lower in ('mariadb', 'mysql') or 'mariadb' in db_lower or 'mysql' in db_lower:
        # use pymysql driver; include init_command to ensure database is selected
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?init_command=SET sql_mode='STRICT_TRANS_TABLES'"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def test_connection(db_type: str, host: str, port: int, database: str,
                    user: str, password: str, driver_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Attempt to connect to the database; return (success, error_message).

    Returns (True, None) on success, or (False, error_string) on failure.
    The error message includes exception details for debugging.
    """
    # Validate required parameters
    if not host or not host.strip():
        return False, "Host name cannot be empty"
    if not database or not str(database).strip():
        return False, "Database name cannot be empty"
    if not user or not user.strip():
        return False, "User name cannot be empty"
    
    try:
        url = _make_url(db_type, host, port, database, user, password, driver_path)
        # Add connection timeout to fail faster if host is unreachable
        connect_args = {}
        if "mysql" in url.lower():
            # For PyMySQL: connect_timeout in seconds, plus read/write timeouts
            connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
        connect_kwargs = {"pool_pre_ping": True}
        if connect_args:
            connect_kwargs["connect_args"] = connect_args
        engine = create_engine(url, **connect_kwargs)
        with engine.connect() as conn:
            # execute a lightweight statement
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)


def get_table_columns(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, table_name: str,
                      driver_path: Optional[str] = None) -> List[str]:
    """Return a list of column names for the given table.

    Raises SQLAlchemyError on failure.
    """
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
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
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    with engine.connect() as conn:
        try:
            q_table = _quote_table_identifier(db_type, table_name)
            result = conn.execute(text(f"SELECT * FROM {q_table} LIMIT 1"))
            row = result.fetchone()
            if row is not None:
                return dict(row._mapping)
        except SQLAlchemyError:
            pass
    return None


def get_table_names(db_type: str, host: str, port: int, database: str,
                    user: str, password: str,
                    driver_path: Optional[str] = None) -> List[str]:
    """Return a list of table names in the specified database.

    Raises SQLAlchemyError on failure.  Useful for populating a table selector
    in the UI.
    """
    if not database or not str(database).strip():
        raise ValueError("Database name cannot be empty when fetching table names")
    
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_database_names(db_type: str, host: str, port: int,
                       user: str, password: str,
                       driver_path: Optional[str] = None) -> List[str]:
    """Return a list of accessible database names on the server.

    Connects without selecting a specific database and runs SHOW DATABASES
    (MySQL/MariaDB) or queries sys.databases (MSSQL).

    Raises PermissionError if the user lacks the required privilege.
    Raises ValueError or SQLAlchemyError for connection failures.
    """
    db_lower = db_type.lower()
    if 'mssql' in db_lower or 'sqlserver' in db_lower:
        try:
            import pymssql  # type: ignore
            url = f"mssql+pymssql://{user}:{password}@{host}:{port}/master"
        except ImportError:
            drv = driver_path or "ODBC Driver 17 for SQL Server"
            drv_enc = drv.replace(' ', '+')
            url = f"mssql+pyodbc://{user}:{password}@{host}:{port}/master?driver={drv_enc}"
        engine = create_engine(url)
        with engine.connect() as conn:
            try:
                result = conn.execute(text(
                    "SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"
                ))
                return [row[0] for row in result]
            except SQLAlchemyError as e:
                err_str = str(e).lower()
                if "permission" in err_str or "denied" in err_str or "privilege" in err_str:
                    raise PermissionError(
                        "Insufficient permissions to list databases. "
                        "Please enter the database name manually."
                    ) from e
                raise
    else:
        # MySQL/MariaDB: connect without selecting a database
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/"
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
        engine = create_engine(url, connect_args=connect_args)
        with engine.connect() as conn:
            try:
                result = conn.execute(text("SHOW DATABASES"))
                system_dbs = {'information_schema', 'performance_schema', 'mysql', 'sys'}
                return [row[0] for row in result if row[0].lower() not in system_dbs]
            except SQLAlchemyError as e:
                err_str = str(e).lower()
                if "access denied" in err_str or "1044" in str(e) or "1045" in str(e):
                    raise PermissionError(
                        "Insufficient permissions to list databases. "
                        "Please enter the database name manually."
                    ) from e
                raise


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
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    with engine.connect() as conn:
        q_table = _quote_table_identifier(db_type, table_name)
        sql = f"SELECT * FROM {q_table}"
        if limit:
            sql += f" LIMIT {limit}"
        result = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchall()]
    return rows


def get_query_rows(db_type: str, host: str, port: int, database: str,
                   user: str, password: str, query: str,
                   driver_path: Optional[str] = None,
                   limit: Optional[int] = None) -> List[dict]:
    """Return rows from a custom SELECT query as a list of dicts.

    The caller is responsible for supplying a valid read-only query.
    If ``limit`` is provided, this method truncates the returned list in-memory.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = [dict(r._mapping) for r in result.fetchall()]
        if limit and limit > 0:
            rows = rows[:limit]
        return rows


def get_query_columns(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, query: str,
                      driver_path: Optional[str] = None) -> List[str]:
    """Return result column names for a custom query."""
    rows = get_query_rows(db_type, host, port, database, user, password, query, driver_path, limit=1)
    if not rows:
        return []
    return list(rows[0].keys())


def get_query_sample(db_type: str, host: str, port: int, database: str,
                     user: str, password: str, query: str,
                     driver_path: Optional[str] = None) -> Optional[dict]:
    """Return one sample row for a custom query, or None if no rows."""
    rows = get_query_rows(db_type, host, port, database, user, password, query, driver_path, limit=1)
    return rows[0] if rows else None


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
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        cols_def = ", ".join(f"{_quote_identifier(db_type, col)} TEXT" for col in columns)
        q_table = _quote_table_identifier(db_type, table_name)
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {q_table} ({cols_def})"))


def add_missing_columns(db_type: str, host: str, port: int, database: str,
                       user: str, password: str, table_name: str,
                       required_columns: List[str],
                       driver_path: Optional[str] = None) -> List[str]:
    """Add missing columns to an existing table.
    
    Checks which columns from required_columns don't exist in the table,
    and adds them as TEXT columns.
    
    Returns a list of column names that were added.
    """
    if not required_columns:
        return []
    
    url = _make_url(db_type, host, port, database, user, password, driver_path)
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    
    try:
        inspector = inspect(engine)
        if not inspector.has_table(table_name):
            return []
        
        # Get existing columns
        existing_cols = {c.get('name') for c in inspector.get_columns(table_name)}
        
        # Find missing columns
        missing_cols = [col for col in required_columns if col not in existing_cols]
        
        if not missing_cols:
            return []
        
        # Add missing columns
        q_table = _quote_table_identifier(db_type, table_name)
        with engine.begin() as conn:
            for col in missing_cols:
                q_col = _quote_identifier(db_type, col)
                conn.execute(text(f"ALTER TABLE {q_table} ADD COLUMN {q_col} TEXT"))
        
        return missing_cols
    except Exception:
        # If we can't add columns, return empty list
        return []


def rename_table_columns(db_type: str, host: str, port: int, database: str,
                         user: str, password: str, table_name: str,
                         rename_map: dict,
                         driver_path: Optional[str] = None):
    """Rename columns on an existing table.

    ``rename_map`` should be {old_name: new_name}. This helper currently
    supports MariaDB/MySQL via ``CHANGE COLUMN`` and preserves the existing
    SQLAlchemy-reflected type/nullability for each column.
    """
    if not rename_map:
        return

    db_lower = (db_type or '').lower()
    if not (db_lower in ('mariadb', 'mysql') or 'mariadb' in db_lower or 'mysql' in db_lower):
        raise NotImplementedError("Column rename migration is currently implemented for MariaDB/MySQL only")

    url = _make_url(db_type, host, port, database, user, password, driver_path)
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    inspector = inspect(engine)
    meta_cols = {c.get('name'): c for c in inspector.get_columns(table_name)}
    q_table = _quote_table_identifier(db_type, table_name)

    with engine.begin() as conn:
        for old_name, new_name in rename_map.items():
            if not old_name or not new_name or old_name == new_name:
                continue
            col_meta = meta_cols.get(old_name)
            if not col_meta:
                continue
            col_type = str(col_meta.get('type', 'TEXT'))
            null_sql = "NULL" if bool(col_meta.get('nullable', True)) else "NOT NULL"
            q_old = _quote_identifier(db_type, old_name)
            q_new = _quote_identifier(db_type, new_name)
            conn.execute(text(f"ALTER TABLE {q_table} CHANGE COLUMN {q_old} {q_new} {col_type} {null_sql}"))


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
    connect_args = {}
    if "mysql" in url.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5}
    engine = create_engine(url, connect_args=connect_args if connect_args else None) if connect_args else create_engine(url)
    q_table = _quote_table_identifier(db_type, table_name)
    with engine.begin() as conn:
        for row in rows:
            if not row:
                continue
            col_items = list(row.items())
            q_cols = []
            placeholders = []
            bind_params = {}
            for idx, (col_name, value) in enumerate(col_items):
                bind_name = f"p{idx}"
                q_cols.append(_quote_identifier(db_type, col_name))
                placeholders.append(f":{bind_name}")
                bind_params[bind_name] = value
            cols_sql = ", ".join(q_cols)
            params_sql = ", ".join(placeholders)
            conn.execute(text(f"INSERT INTO {q_table} ({cols_sql}) VALUES ({params_sql})"), bind_params)
