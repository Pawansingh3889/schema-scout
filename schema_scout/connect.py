"""SQL Server connection helpers.

``pyodbc`` is imported lazily so the rest of the package (model, infer,
classify, render) imports and unit-tests without a driver installed.
"""
from __future__ import annotations

import os

# Preference order: newest first, then fall back to anything that looks like
# a SQL Server driver.
_PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


def pick_driver() -> str:
    import pyodbc

    available = set(pyodbc.drivers())
    for d in _PREFERRED_DRIVERS:
        if d in available:
            return d
    for d in available:
        if "SQL Server" in d:
            return d
    raise RuntimeError(
        "No SQL Server ODBC driver found. Install 'ODBC Driver 18 for SQL "
        "Server' (Microsoft download) or set SCHEMA_SCOUT_CONN to a full "
        "connection string."
    )


def build_conn_str(
    server: str,
    database: str,
    user: str | None = None,
    password: str | None = None,
    encrypt: bool = True,
) -> str:
    """Build an ODBC connection string.

    Windows auth (Trusted_Connection) is used when ``user`` is omitted, which
    is the common case for an on-prem SQL Server accessed from a domain
    machine.
    """
    driver = pick_driver()
    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}"]
    if user:
        parts += [f"UID={user}", f"PWD={password or ''}"]
    else:
        parts.append("Trusted_Connection=yes")
    # Driver 18 defaults to Encrypt=yes and validates the cert; on-prem
    # servers usually have a self-signed cert, so trust it explicitly.
    if "18" in driver:
        parts.append("Encrypt=yes" if encrypt else "Encrypt=no")
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts) + ";"


def connect(
    conn_str: str | None = None,
    *,
    server: str | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    readonly: bool = True,
):
    """Open a connection.

    Resolution order: explicit ``conn_str`` -> ``SCHEMA_SCOUT_CONN`` env var
    -> built from ``server``/``database``. Opens read-only by default;
    schema-scout only ever issues SELECTs.
    """
    import pyodbc

    cs = conn_str or os.environ.get("SCHEMA_SCOUT_CONN")
    if not cs:
        if not (server and database):
            raise ValueError(
                "Provide conn_str, set SCHEMA_SCOUT_CONN, or pass "
                "server and database."
            )
        cs = build_conn_str(server, database, user, password)
    conn = pyodbc.connect(cs, readonly=readonly)
    return conn
