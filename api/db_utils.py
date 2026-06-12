"""Helper functions for database connectivity and metadata retrieval.

This module provides JDBC-only connectivity for database import/export.
Supported backends are MSSQL, MySQL, and Oracle via ``jaydebeapi`` +
``JPype1`` and vendor JDBC drivers (.jar files).
"""
import os
import re
import platform
import subprocess
from pathlib import Path
from typing import Tuple, List, Optional

from sqlalchemy import text


_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent


def _ensure_jdk_native_access_option() -> None:
    """Enable native access for JPype on modern JDKs to suppress warnings.

    JDK 22+ warns when JNI/native access is not explicitly enabled.
    Setting this option before JVM startup keeps runtime output clean.
    """
    option = "--enable-native-access=ALL-UNNAMED"
    current = (os.environ.get("JDK_JAVA_OPTIONS") or "").strip()
    if option in current:
        return
    os.environ["JDK_JAVA_OPTIONS"] = f"{current} {option}".strip()


def _is_java_home_discovery_error(text: str) -> bool:
    """Return True when a JPype/JVM error indicates macOS java_home lookup failed."""
    msg = str(text or "").lower()
    return (
        '/usr/libexec/java_home' in msg
        or 'command' in msg and 'java_home' in msg and 'non-zero exit status' in msg
    )


def _get_java_runtime_error_details() -> str:
    """Return actionable guidance when no JVM is discoverable for JDBC use."""
    return (
        "No Java runtime was discovered for JDBC operations.\n\n"
        "On macOS, install a JDK and set JAVA_HOME before launching the app:\n"
        "  brew install openjdk\n"
        "  export JAVA_HOME=/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home\n"
        "  export PATH=\"$JAVA_HOME/bin:$PATH\"\n\n"
        "Then restart the app so the environment is picked up."
    )


def _ensure_java_home_macos_quiet() -> bool:
    """Quietly discover JAVA_HOME on macOS; return False when unavailable."""
    if platform.system() != 'Darwin':
        return True
    if (os.environ.get('JAVA_HOME') or '').strip():
        return True
    try:
        probe = subprocess.run(
            ['/usr/libexec/java_home'],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            return False
        discovered = (probe.stdout or '').strip()
        if discovered:
            os.environ['JAVA_HOME'] = discovered
            return True
        return False
    except Exception:
        return False


def get_java_runtime_status() -> dict:
    """Return JVM discovery status for startup preflight checks.

    This function does not start the JVM. It only verifies whether a
    usable JVM path is discoverable in the current process environment.
    """
    # On macOS, pre-check java_home quietly to avoid noisy stderr output from
    # downstream JVM discovery calls when Java is missing.
    if not _ensure_java_home_macos_quiet():
        return {'available': False, 'message': _get_java_runtime_error_details()}

    try:
        import jpype  # type: ignore
    except Exception:
        return {
            'available': False,
            'message': (
                "JDBC features require JPype1 and a Java runtime. "
                "Install with: pip install jaydebeapi JPype1"
            ),
        }

    try:
        jvm_path = jpype.getDefaultJVMPath()
    except Exception as exc:
        err = str(exc)
        if _is_java_home_discovery_error(err):
            return {'available': False, 'message': _get_java_runtime_error_details()}
        return {
            'available': False,
            'message': f"Java runtime not discoverable for JDBC: {err}",
        }

    if not jvm_path or not os.path.exists(str(jvm_path)):
        return {
            'available': False,
            'message': _get_java_runtime_error_details(),
        }

    return {
        'available': True,
        'message': '',
        'jvm_path': str(jvm_path),
    }


def check_available_drivers() -> dict:
    """Check JDBC prerequisites and return install/download guidance."""
    drivers = {
        'jaydebeapi': {
            'available': False,
            'url': 'https://pypi.org/project/JayDeBeApi/',
            'purpose': 'JDBC bridge for MSSQL, MySQL, and Oracle',
            'install': 'pip install jaydebeapi JPype1',
        },
        'jdbc_jars': {
            'available': False,
            'url': 'https://learn.microsoft.com/en-us/sql/connect/jdbc/download-microsoft-jdbc-driver-for-sql-server',
            'purpose': 'Vendor JDBC .jar files (mssql-jdbc / mysql-connector-j / ojdbc)',
            'install': 'Download and set Driver Path to a .jar file in the DB connection dialog',
        },
    }

    # jaydebeapi import name differs from the PyPI package name
    try:
        import jaydebeapi  # type: ignore  # noqa: F401
        drivers['jaydebeapi']['available'] = True
    except ImportError:
        pass

    missing = [d for d in drivers if not drivers[d]['available']]

    return {
        'jaydebeapi': drivers['jaydebeapi'],
        'jdbc_jars': drivers['jdbc_jars'],
        'missing': missing,
        'driver_info': drivers,
    }


def _get_mssql_driver_error() -> str:
    """Generate JDBC-only setup guidance for MSSQL."""
    return (
        "MSSQL database support is JDBC-only in this app.\n\n"
        "Required Python packages:\n"
        "  pip install jaydebeapi JPype1\n\n"
        "Required JDBC jar:\n"
        "  https://learn.microsoft.com/en-us/sql/connect/jdbc/download-microsoft-jdbc-driver-for-sql-server\n\n"
        "Set Driver Path to the mssql-jdbc .jar file in the DB connection dialog."
    )


def _get_mysql_driver_error() -> str:
    """Generate JDBC-only setup guidance for MySQL."""
    return (
        "MySQL database support is JDBC-only in this app.\n\n"
        "Required Python packages:\n"
        "  pip install jaydebeapi JPype1\n\n"
        "Required JDBC jar (MySQL Connector/J):\n"
        "  https://dev.mysql.com/downloads/connector/j/\n\n"
        "Set Driver Path to: drivers/mysql/mysql-connector-j-9.0.0.jar\n\n"
        "Recommended folder layout:\n"
        "  p1-usermanager/drivers/mysql/mysql-connector-j-9.0.0.jar"
    )


def _get_oracle_driver_error() -> str:
    """Generate JDBC-only setup guidance for Oracle."""
    return (
        "Oracle database support is JDBC-only in this app.\n\n"
        "Required Python packages:\n"
        "  pip install jaydebeapi JPype1\n\n"
        "Required JDBC jar (Oracle ojdbc):\n"
        "  https://www.oracle.com/database/technologies/appdev/jdbc-downloads.html\n\n"
        "Set Driver Path to the ojdbc .jar file in the DB connection dialog."
    )


def _normalize_db_type(db_type: str) -> str:
    """Normalize display labels/aliases into one of mssql/mysql/oracle."""
    raw = (db_type or "").strip().lower()
    if raw in ('mssql', 'sqlserver') or 'mssql' in raw or 'sql server' in raw:
        return 'mssql'
    if raw in ('mysql', 'mariadb') or 'mysql' in raw or 'mariadb' in raw:
        return 'mysql'
    if raw in ('oracle',) or 'oracle' in raw:
        return 'oracle'
    raise ValueError(f"Unsupported database type: {db_type}")


def _normalize_encrypt_mode(encrypt_mode: Optional[str]) -> str:
    """Normalize MSSQL encryption mode to one of auto/on/off."""
    if isinstance(encrypt_mode, bool):
        # Backward compatibility: legacy boolean values were historically
        # treated as "enable encryption" without an explicit strict mode.
        # Map True to Auto (secure-first with fallback) and False to Off.
        return 'auto' if encrypt_mode else 'off'
    raw = (encrypt_mode or "").strip().lower()
    if not raw:
        return 'auto'
    if raw in ('auto', 'default'):
        return 'auto'
    if raw in ('on', 'required', 'strict'):
        return 'on'
    if raw in ('true', 'yes', '1', 'enabled'):
        # Keep legacy truthy text values in Auto for safer behavior with
        # mixed SQL Server TLS endpoint compatibility.
        return 'auto'
    if raw in ('off', 'false', 'no', '0', 'disabled'):
        return 'off'
    return 'auto'


# ---------------------------------------------------------------------------
# JDBC support helpers and engine wrapper
# ---------------------------------------------------------------------------

def _is_jdbc_jar(driver_path: Optional[str]) -> bool:
    """Return True if driver_path points to a JDBC .jar file."""
    return bool(driver_path and str(driver_path).strip().lower().endswith('.jar'))


def _resolve_driver_jar_path(driver_path: str) -> str:
    """Resolve driver jar path to an existing absolute path.

    Resolution order for relative paths:
    1) current working directory
    2) project root directory
    """
    raw = str(driver_path or "").strip()
    if not raw:
        raise FileNotFoundError("Driver Path is empty")

    expanded = Path(raw).expanduser()
    candidates = [expanded] if expanded.is_absolute() else [Path.cwd() / expanded, _PROJECT_ROOT / expanded]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".jar":
            return str(candidate.resolve())

    checked = "\n".join(f"  - {str(c)}" for c in candidates)
    raise FileNotFoundError(
        "JDBC driver jar was not found at the specified Driver Path. Checked:\n"
        f"{checked}"
    )


def _sqlalchemy_to_jdbc(sql: str, params: dict) -> tuple:
    """Convert SQLAlchemy named bind params (:name) to JDBC positional '?'.

    Returns (converted_sql, ordered_values_list).
    """
    if not params:
        return sql, []
    values: list = []

    def _replace(m):
        values.append(params[m.group(1)])
        return '?'

    return re.sub(r':(\w+)', _replace, sql), values


class _JDBCRow:
    """Mimics SQLAlchemy Row._mapping for jaydebeapi cursor rows."""
    __slots__ = ('_data',)

    def __init__(self, columns: list, values):
        self._data = dict(zip(columns, values))

    @property
    def _mapping(self):
        return self._data


class _JDBCResult:
    """Mimics SQLAlchemy Result for a jaydebeapi cursor."""

    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [desc[0] for desc in (cursor.description or [])]

    def keys(self) -> list:
        return list(self._columns)

    def fetchone(self):
        row = self._cursor.fetchone()
        return _JDBCRow(self._columns, row) if row is not None else None

    def fetchall(self) -> list:
        return [_JDBCRow(self._columns, row) for row in self._cursor.fetchall()]

    def __iter__(self):
        while True:
            row = self._cursor.fetchone()
            if row is None:
                break
            yield _JDBCRow(self._columns, row)


class _JDBCConnection:
    """Mimics SQLAlchemy Connection for a jaydebeapi raw connection."""

    def __init__(self, raw_conn, auto_close: bool = True):
        self._conn = raw_conn
        self._auto_close = auto_close

    def execute(self, stmt, params=None):
        sql = stmt.text if hasattr(stmt, 'text') else str(stmt)
        cursor = self._conn.cursor()
        if params:
            jdbc_sql, values = _sqlalchemy_to_jdbc(sql, params)
            cursor.execute(jdbc_sql, values)
        else:
            cursor.execute(sql)
        return _JDBCResult(cursor)

    def execution_options(self, **kwargs):
        return self  # stream_results not applicable to JDBC; return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                # Only commit if autocommit is disabled
                try:
                    if not self._conn.jconn.getAutoCommit():
                        self._conn.commit()
                except Exception:
                    pass  # best-effort; autocommit likely enabled
            else:
                # Only rollback if autocommit is disabled
                try:
                    if not self._conn.jconn.getAutoCommit():
                        self._conn.rollback()
                except Exception:
                    pass  # best-effort
        finally:
            if self._auto_close:
                self._conn.close()
        return False


class _JDBCInspector:
    """Mimics SQLAlchemy Inspector for JDBC connections."""

    def __init__(self, engine: '_JDBCEngine'):
        self._engine = engine

    def get_columns(self, table_name: str) -> list:
        db_kind = self._engine._db_kind
        raw = self._engine._raw_connect()
        try:
            cursor = raw.cursor()
            if db_kind == 'mssql':
                cursor.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                    [table_name],
                )
            elif db_kind == 'mysql':
                cursor.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                    [self._engine._database, table_name],
                )
            else:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM USER_TAB_COLUMNS "
                    "WHERE TABLE_NAME = ? ORDER BY COLUMN_ID",
                    [str(table_name or '').upper()],
                )
            return [{'name': row[0]} for row in cursor.fetchall()]
        finally:
            raw.close()

    def get_table_names(self) -> list:
        db_kind = self._engine._db_kind
        raw = self._engine._raw_connect()
        try:
            cursor = raw.cursor()
            if db_kind == 'mssql':
                cursor.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
                )
            elif db_kind == 'mysql':
                cursor.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = ? AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
                    [self._engine._database],
                )
            else:
                cursor.execute("SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME")
            return [row[0] for row in cursor.fetchall()]
        finally:
            raw.close()

    def has_table(self, table_name: str) -> bool:
        db_kind = self._engine._db_kind
        raw = self._engine._raw_connect()
        try:
            cursor = raw.cursor()
            if db_kind == 'mssql':
                cursor.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME = ?",
                    [table_name],
                )
            elif db_kind == 'mysql':
                cursor.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = ? AND TABLE_TYPE='BASE TABLE' AND TABLE_NAME = ?",
                    [self._engine._database, table_name],
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = ?",
                    [str(table_name or '').upper()],
                )
            row = cursor.fetchone()
            return bool(row and row[0] > 0)
        finally:
            raw.close()


class _JDBCEngine:
    """Mimics SQLAlchemy Engine for JDBC connections via jaydebeapi."""

    def __init__(self, db_kind: str, host: str, port: int, database: str,
                 user: str, password: str, jar_path: str,
                 encrypt_mode: Optional[str] = None):
        self._db_kind = db_kind
        self._host = host
        self._port = int(port)
        self._database = database
        self._user = user
        self._password = password
        self._jar_path = jar_path
        self._encrypt_mode = _normalize_encrypt_mode(encrypt_mode)
        if db_kind == 'mssql':
            self._driver_class = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
            base_url = f"jdbc:sqlserver://{host}:{int(port)};databaseName={database};"
            if self._encrypt_mode == 'off':
                self._jdbc_url = base_url + "encrypt=false"
                self._jdbc_url_insecure = self._jdbc_url
            else:
                self._jdbc_url = base_url + "encrypt=true;trustServerCertificate=true"
                self._jdbc_url_insecure = base_url + "encrypt=false"
        elif db_kind == 'mysql':
            self._driver_class = "com.mysql.cj.jdbc.Driver"
            self._jdbc_url = (
                f"jdbc:mysql://{host}:{int(port)}/{database}"
                "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"
            )
            self._jdbc_url_insecure = self._jdbc_url
        elif db_kind == 'oracle':
            self._driver_class = "oracle.jdbc.OracleDriver"
            self._jdbc_url = f"jdbc:oracle:thin:@//{host}:{int(port)}/{database}"
            self._jdbc_url_insecure = self._jdbc_url
        else:
            raise ValueError(f"Unsupported JDBC database type: {db_kind}")

    def _raw_connect(self):
        import jaydebeapi  # type: ignore
        _ensure_jdk_native_access_option()
        if not _ensure_java_home_macos_quiet():
            raise RuntimeError(_get_java_runtime_error_details())
        jvm_bootstrap_error = None
        try:
            import jpype  # type: ignore
            if jpype.isJVMStarted():
                # If JVM was already started earlier in this process, make sure
                # the currently selected vendor jar is still on the classpath.
                jpype.addClassPath(self._jar_path)
            else:
                # JPype starts the JVM via JNI (not the java launcher), so
                # process env vars like JDK_JAVA_OPTIONS may not reliably apply.
                # Start JVM explicitly with native-access enabled to avoid
                # restricted-method warnings on modern JDKs.
                jpype.startJVM(
                    jpype.getDefaultJVMPath(),
                    "--enable-native-access=ALL-UNNAMED",
                    classpath=[self._jar_path],
                )
        except Exception as exc:
            jvm_bootstrap_error = str(exc)
            # Best effort only; jaydebeapi.connect below will still raise
            # actionable errors if class loading fails.
            pass

        def _connect(url: str):
            return jaydebeapi.connect(
                self._driver_class,
                url,
                [self._user, self._password],
                self._jar_path,
            )

        try:
            return _connect(self._jdbc_url)
        except Exception as exc:
            msg = str(exc)
            if _is_java_home_discovery_error(msg) or _is_java_home_discovery_error(jvm_bootstrap_error):
                raise RuntimeError(_get_java_runtime_error_details()) from exc
            if self._db_kind == 'mssql':
                ssl_error = (
                    'could not establish a secure connection' in msg.lower()
                    or 'unexpected_message' in msg.lower()
                    or ('"encrypt" property is set to "true"' in msg and 'trustservercertificate' in msg.lower())
                )
                if ssl_error and self._encrypt_mode == 'auto':
                    try:
                        return _connect(self._jdbc_url_insecure)
                    except Exception:
                        pass
                if ssl_error and self._encrypt_mode == 'on':
                    raise RuntimeError(
                        "MSSQL SSL/TLS handshake failed while Encrypt Mode is 'On'. "
                        "Try setting Encrypt Mode to 'Auto' (secure-first fallback) or 'Off' "
                        "for servers that do not support TLS on this endpoint."
                    ) from exc
            if "Class" in msg and "is not found" in msg:
                raise RuntimeError(
                    f"JDBC driver class '{self._driver_class}' was not found using jar '{self._jar_path}'. "
                    "Verify Driver Path points to the correct vendor JDBC jar for the selected DB type."
                ) from exc
            raise

    def connect(self) -> '_JDBCConnection':
        return _JDBCConnection(self._raw_connect(), auto_close=True)

    def begin(self) -> '_JDBCConnection':
        raw = self._raw_connect()
        try:
            raw.jconn.setAutoCommit(False)
        except Exception:
            pass  # best-effort; __exit__ commits/rolls back
        return _JDBCConnection(raw, auto_close=True)

    def inspect(self) -> '_JDBCInspector':
        return _JDBCInspector(self)


# ---------------------------------------------------------------------------
# Quoted identifier helpers
# ---------------------------------------------------------------------------

def _quote_identifier(db_type: str, ident: str) -> str:
    """Return a safely quoted SQL identifier for the target database type.

    This treats ``ident`` as a single identifier token. It is suitable for
    column names, including legacy names that may themselves contain dots.
    """
    db_kind = _normalize_db_type(db_type)
    token = str(ident or "")
    if not token:
        raise ValueError("Identifier cannot be empty")

    if db_kind == 'mssql':
        return f"[{token.replace(']', ']]')}]"
    if db_kind == 'oracle':
        return f'"{token.replace("\"", "\"\"")}"'
    return f"`{token.replace('`', '``')}`"


def _quote_table_identifier(db_type: str, ident: str) -> str:
    """Return a quoted table identifier, supporting dotted schema.table paths.
    
    Strips whitespace from identifiers to prevent SQL errors.
    Validates against basic SQL injection patterns.
    """
    ident = str(ident or "").strip()
    
    # Basic SQL injection detection - reject suspicious patterns
    suspicious_patterns = [';', '--', '/*', '*/', 'xp_', 'sp_', 'DROP', 'DELETE', 'INSERT', 'UPDATE', 'EXEC']
    ident_upper = ident.upper()
    for pattern in suspicious_patterns:
        if pattern.upper() in ident_upper:
            raise ValueError(f"Invalid characters in identifier: {pattern}")
    
    parts = [p.strip() for p in ident.split('.') if p.strip()]
    if not parts:
        raise ValueError("Identifier cannot be empty")
    return '.'.join(_quote_identifier(db_type, p) for p in parts)


def _make_engine(db_type: str, host: str, port: int, database: str,
                 user: str, password: str,
                 driver_path: Optional[str] = None,
                 encrypt_mode: Optional[str] = None):
    """Return a JDBC engine for MSSQL, MySQL, or Oracle.

    ``driver_path`` must point to a JDBC .jar file.
    """
    db_kind = _normalize_db_type(db_type)
    if not _is_jdbc_jar(driver_path):
        if db_kind == 'mssql':
            raise ImportError(_get_mssql_driver_error())
        if db_kind == 'mysql':
            raise ImportError(_get_mysql_driver_error())
        raise ImportError(_get_oracle_driver_error())
    try:
        import jaydebeapi  # type: ignore  # noqa: F401
    except ImportError:
        raise ImportError(
            "JDBC support requires 'jaydebeapi' and 'JPype1' to be installed.\n"
            "  pip install jaydebeapi JPype1\n"
            "  https://pypi.org/project/JayDeBeApi/"
        )

    if not host or not host.strip():
        raise ValueError("Host name cannot be empty")
    if not user or not user.strip():
        raise ValueError("User name cannot be empty")
    if not database or not str(database).strip():
        raise ValueError("Database/service name cannot be empty")

    default_db = {
        'mssql': 'master',
        'mysql': 'mysql',
        'oracle': 'orcl',
    }
    db_name = (database or '').strip() or default_db[db_kind]
    resolved_jar = _resolve_driver_jar_path(str(driver_path).strip())
    return _JDBCEngine(
        db_kind,
        host.strip(),
        int(port),
        db_name,
        user.strip(),
        password,
        resolved_jar,
        encrypt_mode=encrypt_mode,
    )


def _inspect_engine(engine):
    """Return the inspector for a JDBC engine."""
    return engine.inspect()


def test_connection(db_type: str, host: str, port: int, database: str,
                    user: str, password: str,
                    driver_path: Optional[str] = None,
                    encrypt_mode: Optional[str] = None) -> Tuple[bool, Optional[str]]:
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
        engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)


def get_table_columns(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, table_name: str,
                      driver_path: Optional[str] = None,
                      encrypt_mode: Optional[str] = None) -> List[str]:
    """Return a list of column names for the given table.

    Raises an exception on failure.
    """
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    inspector = _inspect_engine(engine)
    cols = inspector.get_columns(table_name)
    return [c['name'] for c in cols]


def get_table_sample(db_type: str, host: str, port: int, database: str,
                     user: str, password: str, table_name: str,
                     driver_path: Optional[str] = None,
                     encrypt_mode: Optional[str] = None) -> Optional[dict]:
    """Return a single row (as dict) from the table, or None if empty.

    Useful for showing sample values next to column names.
    """
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    with engine.connect() as conn:
        try:
            q_table = _quote_table_identifier(db_type, table_name)
            db_kind = _normalize_db_type(db_type)
            if db_kind == 'mssql':
                sql = f"SELECT TOP 1 * FROM {q_table}"
            elif db_kind == 'oracle':
                sql = f"SELECT * FROM {q_table} FETCH FIRST 1 ROWS ONLY"
            else:
                sql = f"SELECT * FROM {q_table} LIMIT 1"
            result = conn.execute(text(sql))
            row = result.fetchone()
            if row is not None:
                return dict(row._mapping)
        except Exception:
            pass
    return None


def get_table_names(db_type: str, host: str, port: int, database: str,
                    user: str, password: str,
                    driver_path: Optional[str] = None,
                    encrypt_mode: Optional[str] = None) -> List[str]:
    """Return a list of table names in the specified database.

    Useful for populating a table selector in the UI.
    """
    if not database or not str(database).strip():
        raise ValueError("Database name cannot be empty when fetching table names")

    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    inspector = _inspect_engine(engine)
    return inspector.get_table_names()


def get_database_names(db_type: str, host: str, port: int,
                       user: str, password: str,
                       driver_path: Optional[str] = None,
                       encrypt_mode: Optional[str] = None) -> List[str]:
    """Return a list of accessible database names on the server.

    Connects without selecting a specific database and runs SHOW DATABASES
    (MySQL) or queries sys.databases (MSSQL).

    Raises PermissionError if the user lacks the required privilege.
    Raises ValueError or runtime connection errors for failures.
    """
    db_kind = _normalize_db_type(db_type)
    if db_kind == 'oracle':
        # Oracle does not expose a simple cross-tenant "database list" query in this flow.
        return []

    base_database = 'master' if db_kind == 'mssql' else 'mysql'
    engine = _make_engine(db_type, host, port, base_database, user, password, driver_path, encrypt_mode)
    with engine.connect() as conn:
        try:
            if db_kind == 'mssql':
                result = conn.execute(text("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"))
                return [row._mapping.get('name') or list(row._mapping.values())[0] for row in result]

            result = conn.execute(text("SHOW DATABASES"))
            system_dbs = {'information_schema', 'performance_schema', 'mysql', 'sys'}
            names = []
            for row in result:
                value = list(row._mapping.values())[0]
                if str(value).lower() not in system_dbs:
                    names.append(value)
            return names
        except Exception as e:
            err_str = str(e).lower()
            if "permission" in err_str or "denied" in err_str or "privilege" in err_str or "access denied" in err_str:
                raise PermissionError(
                    "Insufficient permissions to list databases. "
                    "Please enter the database name manually."
                ) from e
            raise


def get_table_rows(db_type: str, host: str, port: int, database: str,
                   user: str, password: str, table_name: str,
                   driver_path: Optional[str] = None,
                   limit: Optional[int] = None,
                   encrypt_mode: Optional[str] = None) -> List[dict]:
    """Return all rows from the specified table as a list of dicts.

    The optional ``limit`` parameter can be used to restrict the number of
    rows returned (useful for previewing large tables). The caller is
    responsible for ensuring the table exists beforehand.
    """
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    with engine.connect() as conn:
        q_table = _quote_table_identifier(db_type, table_name)
        db_kind = _normalize_db_type(db_type)
        if limit and db_kind == 'mssql':
            sql = f"SELECT TOP {int(limit)} * FROM {q_table}"
        elif limit and db_kind == 'oracle':
            sql = f"SELECT * FROM {q_table} FETCH FIRST {int(limit)} ROWS ONLY"
        elif limit:
            sql = f"SELECT * FROM {q_table} LIMIT {limit}"
        else:
            sql = f"SELECT * FROM {q_table}"
        result = conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchall()]
    return rows


def get_query_rows(db_type: str, host: str, port: int, database: str,
                   user: str, password: str, query: str,
                   driver_path: Optional[str] = None,
                   limit: Optional[int] = None,
                   encrypt_mode: Optional[str] = None) -> List[dict]:
    """Return rows from a custom SELECT query as a list of dicts.

    The caller is responsible for supplying a valid read-only query.
    If ``limit`` is provided, this method truncates the returned list in-memory.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = [dict(r._mapping) for r in result.fetchall()]
        if limit and limit > 0:
            rows = rows[:limit]
        return rows


def get_query_columns(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, query: str,
                      driver_path: Optional[str] = None,
                      encrypt_mode: Optional[str] = None) -> List[str]:
    """Return result column names for a custom query."""
    rows = get_query_rows(db_type, host, port, database, user, password, query, driver_path, limit=1, encrypt_mode=encrypt_mode)
    if not rows:
        return []
    return list(rows[0].keys())


def get_query_sample(db_type: str, host: str, port: int, database: str,
                     user: str, password: str, query: str,
                     driver_path: Optional[str] = None,
                     encrypt_mode: Optional[str] = None) -> Optional[dict]:
    """Return one sample row for a custom query, or None if no rows."""
    rows = get_query_rows(db_type, host, port, database, user, password, query, driver_path, limit=1, encrypt_mode=encrypt_mode)
    return rows[0] if rows else None


def stream_table_rows(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, table_name: str,
                      driver_path: Optional[str] = None,
                      batch_size: int = 1000,
                      encrypt_mode: Optional[str] = None):
    """Generator that yields batches of rows from a table.
    
    Instead of loading all rows at once, this streams them in batches
    of ``batch_size`` rows. This is memory-efficient for large tables.
    
    Yields:
        List[dict]: Batches of rows as dictionaries
    """
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)

    with engine.connect() as conn:
        q_table = _quote_table_identifier(db_type, table_name)
        sql = f"SELECT * FROM {q_table}"
        result = conn.execution_options(stream_results=True).execute(text(sql))
        
        batch = []
        for row in result:
            batch.append(dict(row._mapping))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        # Yield remaining rows
        if batch:
            yield batch


def stream_query_rows(db_type: str, host: str, port: int, database: str,
                      user: str, password: str, query: str,
                      driver_path: Optional[str] = None,
                      batch_size: int = 1000,
                      encrypt_mode: Optional[str] = None):
    """Generator that yields batches of rows from a custom query.
    
    Instead of loading all rows at once, this streams them in batches
    of ``batch_size`` rows. This is memory-efficient for large result sets.
    
    Yields:
        List[dict]: Batches of rows as dictionaries
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)

    with engine.connect() as conn:
        result = conn.execution_options(stream_results=True).execute(text(query))
        
        batch = []
        for row in result:
            batch.append(dict(row._mapping))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        # Yield remaining rows
        if batch:
            yield batch


def create_table_if_not_exists(db_type: str, host: str, port: int, database: str,
                               user: str, password: str, table_name: str,
                               columns: List[str],
                               driver_path: Optional[str] = None,
                               encrypt_mode: Optional[str] = None):
    """Create a simple table with given column names if it does not already exist.

    All columns are created with TEXT type for maximum compatibility.  This
    helper is intentionally minimal; callers can always create tables with a
    richer schema if desired.
    """
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    inspector = _inspect_engine(engine)
    if not inspector.has_table(table_name):
        db_kind = _normalize_db_type(db_type)
        if db_kind == 'mssql':
            col_type = 'NVARCHAR(MAX)'
        elif db_kind == 'oracle':
            col_type = 'CLOB'
        else:
            col_type = 'TEXT'
        cols_def = ", ".join(f"{_quote_identifier(db_type, col)} {col_type}" for col in columns)
        q_table = _quote_table_identifier(db_type, table_name)
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {q_table} ({cols_def})"))


def add_missing_columns(db_type: str, host: str, port: int, database: str,
                       user: str, password: str, table_name: str,
                       required_columns: List[str],
                       driver_path: Optional[str] = None,
                       encrypt_mode: Optional[str] = None) -> List[str]:
    """Add missing columns to an existing table.
    
    Checks which columns from required_columns don't exist in the table,
    and adds them as TEXT columns.
    
    Returns a list of column names that were added.
    """
    if not required_columns:
        return []

    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)

    try:
        db_kind = _normalize_db_type(db_type)
        if db_kind == 'mssql':
            col_type = 'NVARCHAR(MAX)'
        elif db_kind == 'oracle':
            col_type = 'CLOB'
        else:
            col_type = 'TEXT'

        inspector = _inspect_engine(engine)
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
                if db_kind == 'oracle':
                    conn.execute(text(f"ALTER TABLE {q_table} ADD ({q_col} {col_type})"))
                else:
                    conn.execute(text(f"ALTER TABLE {q_table} ADD COLUMN {q_col} {col_type}"))
        
        return missing_cols
    except Exception:
        # If we can't add columns, return empty list
        return []


def rename_table_columns(db_type: str, host: str, port: int, database: str,
                         user: str, password: str, table_name: str,
                         rename_map: dict,
                         driver_path: Optional[str] = None,
                         encrypt_mode: Optional[str] = None):
    """Rename columns on an existing table.

    ``rename_map`` should be {old_name: new_name}. This helper currently
    supports MySQL via ``CHANGE COLUMN`` and preserves reflected
    type/nullability for each column.
    """
    if not rename_map:
        return

    db_kind = _normalize_db_type(db_type)
    if db_kind != 'mysql':
        raise NotImplementedError("Column rename migration is currently implemented for MySQL only")

    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
    inspector = _inspect_engine(engine)
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
                driver_path: Optional[str] = None,
                encrypt_mode: Optional[str] = None):
    """Insert a list of rows (dicts) into the specified table.

    Each dict should map column names to values.  This helper performs a simple
    INSERT for each row; it does not attempt to deduplicate or perform updates.
    """
    if not rows:
        return
    engine = _make_engine(db_type, host, port, database, user, password, driver_path, encrypt_mode)
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
