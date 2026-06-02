"""Structure extraction from the SQL Server system catalog.

Every function here is a single set-based query against ``sys.*`` /
``INFORMATION_SCHEMA`` — so a 150-table database costs the same handful of
queries as a 10-table one. None of these read table *data*; row counts come
from catalog statistics, not ``COUNT(*)``.
"""
from __future__ import annotations

from schema_scout.model import Catalog, Column, ForeignKey, Table

# User tables only (exclude system + the dbo.sysdiagrams helper table).
_TABLES_SQL = """
SELECT s.name AS schema_name, t.name AS table_name
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE t.is_ms_shipped = 0 AND t.name <> 'sysdiagrams'
ORDER BY s.name, t.name
"""

# Row counts from partition stats — instant, no table scan.
_ROWCOUNT_SQL = """
SELECT s.name AS schema_name, t.name AS table_name, SUM(p.rows) AS row_count
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id
WHERE p.index_id IN (0, 1) AND t.is_ms_shipped = 0
GROUP BY s.name, t.name
"""

_COLUMNS_SQL = """
SELECT s.name AS schema_name, t.name AS table_name, c.name AS column_name,
       c.column_id, ty.name AS data_type, c.is_nullable,
       c.max_length, c.precision, c.scale, c.is_identity,
       dc.definition AS default_def
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id
"""

_PK_SQL = """
SELECT s.name AS schema_name, t.name AS table_name,
       c.name AS column_name, ic.key_ordinal
FROM sys.indexes i
JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
JOIN sys.tables t ON i.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE i.is_primary_key = 1 AND t.is_ms_shipped = 0
ORDER BY s.name, t.name, ic.key_ordinal
"""

_FK_SQL = """
SELECT fk.name AS fk_name,
       sp.name AS parent_schema, tp.name AS parent_table, cp.name AS parent_column,
       sr.name AS ref_schema,    tr.name AS ref_table,    cr.name AS ref_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.tables tp  ON fkc.parent_object_id = tp.object_id
JOIN sys.schemas sp ON tp.schema_id = sp.schema_id
JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id
                   AND fkc.parent_column_id = cp.column_id
JOIN sys.tables tr  ON fkc.referenced_object_id = tr.object_id
JOIN sys.schemas sr ON tr.schema_id = sr.schema_id
JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id
                   AND fkc.referenced_column_id = cr.column_id
ORDER BY fk.name
"""


def _max_length(raw):
    """sys.columns.max_length is bytes; -1 means MAX. Return chars-ish."""
    if raw is None:
        return None
    if raw == -1:
        return -1  # MAX
    return int(raw)


def extract_tables(cursor) -> list:
    cursor.execute(_TABLES_SQL)
    return [Table(schema=r[0], name=r[1]) for r in cursor.fetchall()]


def extract_row_counts(cursor) -> dict:
    cursor.execute(_ROWCOUNT_SQL)
    return {(r[0], r[1]): int(r[2] or 0) for r in cursor.fetchall()}


def extract_columns(cursor) -> list:
    cursor.execute(_COLUMNS_SQL)
    cols = []
    for r in cursor.fetchall():
        cols.append(
            Column(
                schema=r[0],
                table=r[1],
                name=r[2],
                ordinal=int(r[3]),
                data_type=r[4],
                is_nullable=bool(r[5]),
                max_length=_max_length(r[6]),
                precision=int(r[7]) if r[7] is not None else None,
                scale=int(r[8]) if r[8] is not None else None,
                is_identity=bool(r[9]),
                default=r[10],
            )
        )
    return cols


def extract_primary_keys(cursor) -> dict:
    cursor.execute(_PK_SQL)
    pks: dict = {}
    for r in cursor.fetchall():
        pks.setdefault((r[0], r[1]), []).append(r[2])
    return pks


def extract_foreign_keys(cursor) -> list:
    cursor.execute(_FK_SQL)
    fks = []
    for r in cursor.fetchall():
        fks.append(
            ForeignKey(
                name=r[0],
                parent_schema=r[1],
                parent_table=r[2],
                parent_column=r[3],
                ref_schema=r[4],
                ref_table=r[5],
                ref_column=r[6],
                inferred=False,
                confidence=1.0,
                reason="declared",
            )
        )
    return fks


def extract_catalog(conn) -> Catalog:
    """Assemble a full structural catalog (no profiling)."""
    cur = conn.cursor()
    tables = extract_tables(cur)
    counts = extract_row_counts(cur)
    columns = extract_columns(cur)
    pks = extract_primary_keys(cur)
    fks = extract_foreign_keys(cur)

    tmap = {(t.schema, t.name): t for t in tables}

    for t in tables:
        t.row_count = counts.get((t.schema, t.name), 0)
        t.primary_key = pks.get((t.schema, t.name), [])

    for c in columns:
        t = tmap.get((c.schema, c.table))
        if t is not None:
            t.columns.append(c)

    for t in tables:
        pkset = {p.lower() for p in t.primary_key}
        for c in t.columns:
            c.is_primary_key = c.name.lower() in pkset

    for fk in fks:
        t = tmap.get((fk.parent_schema, fk.parent_table))
        if t is not None:
            t.foreign_keys.append(fk)

    return Catalog(tables=tables, relationships=list(fks))
