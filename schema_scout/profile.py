"""Sampled data profiling.

Profiling is the only phase that reads table data, so it is sample-based and
opt-in. We pull ``TOP (sample_size)`` rows once per table and compute every
column's stats in Python — one round trip per table, not per column. All
resulting counts are relative to the sample (see ``Column.sampled_rows``),
which is honest and keeps cost bounded on a huge database.

By default only the largest / most-connected tables are profiled (the ~20%
that hold ~80% of the value); see ``select_tables_to_profile``.
"""
from __future__ import annotations

from schema_scout.model import Catalog, Column, Table

# Types that MIN/MAX/COUNT(DISTINCT) can't (or shouldn't) be run on directly.
_NON_AGGREGATABLE = {
    "text",
    "ntext",
    "image",
    "xml",
    "geography",
    "geometry",
    "hierarchyid",
    "varbinary",
    "binary",
    "sql_variant",
    "timestamp",
    "rowversion",
}


def select_tables_to_profile(catalog: Catalog, limit: int = 25) -> list:
    """Pick the highest-value tables: most rows, then most referenced.

    Returns up to ``limit`` tables. With 150 tables you rarely want to scan
    them all on the first pass; this front-loads the ones worth reading.
    """
    ref_counts: dict = {}
    for fk in catalog.relationships:
        ref_counts[fk.ref_qualified] = ref_counts.get(fk.ref_qualified, 0) + 1

    def score(t: Table):
        return (t.row_count, ref_counts.get(t.qualified_name, 0))

    return sorted(catalog.tables, key=score, reverse=True)[:limit]


def _quote(schema: str, name: str) -> str:
    return f"[{schema}].[{name}]"


def profile_table(conn, table: Table, sample_size: int = 50000, top_k: int = 10) -> Table:
    """Profile one table in place. Requires pandas; imported lazily."""
    import pandas as pd

    cur = conn.cursor()
    sql = f"SELECT TOP ({int(sample_size)}) * FROM {_quote(table.schema, table.name)}"
    cur.execute(sql)
    col_names = [d[0] for d in cur.description]
    rows = cur.fetchall()
    df = pd.DataFrame.from_records([tuple(r) for r in rows], columns=col_names)
    sampled = len(df)

    for col in table.columns:
        if col.name not in df.columns:
            continue
        s = df[col.name]
        col.profile_mode = "sampled"
        col.sampled_rows = sampled
        col.null_count = int(s.isna().sum())
        nonnull = s.dropna()
        col.distinct_count = int(nonnull.nunique())
        if not nonnull.empty:
            try:
                col.min_value = str(nonnull.min())
                col.max_value = str(nonnull.max())
            except (TypeError, ValueError):
                pass
            try:
                vc = nonnull.value_counts().head(top_k)
                col.sample_values = [str(v) for v in vc.index.tolist()]
            except (TypeError, ValueError):
                col.sample_values = [str(v) for v in nonnull.head(top_k).tolist()]
    return table


def profile_catalog(conn, catalog: Catalog, limit: int = 25, sample_size: int = 50000) -> list:
    """Profile the top ``limit`` tables. Returns the tables profiled."""
    targets = select_tables_to_profile(catalog, limit=limit)
    done = []
    for t in targets:
        if t.row_count == 0:
            continue
        profile_table(conn, t, sample_size=sample_size)
        done.append(t)
    return done


# --- exact (non-sampled) profiling --------------------------------------
#
# Sampled profiling is fast but its distinct counts are estimates, so a
# column can look unique in a 50k sample yet have duplicates in the full
# table. Exact mode runs SQL aggregates over the whole table for accurate
# null counts, distinct counts and ranges. It's heavier, so it's opt-in and
# usually pointed at key-like columns only (to confirm a real primary key).
# Top-N value lists are not computed in exact mode (that needs a GROUP BY per
# column); use sampled mode for those.


def can_aggregate(column: Column) -> bool:
    """Whether MIN/MAX/COUNT(DISTINCT) is safe on this column's type."""
    t = column.data_type.lower()
    if t in _NON_AGGREGATABLE:
        return False
    # MAX-length strings can't be DISTINCT-counted or MIN/MAX'd
    if t in {"varchar", "nvarchar", "char", "nchar"} and column.max_length == -1:
        return False
    return True


def key_like_columns(table: Table) -> list:
    """Names of columns worth an exact check for key-ness.

    Declared PK / identity columns, plus anything named like a key. A heuristic
    — a few false positives just mean a couple of extra columns get profiled.
    """
    out = []
    for c in table.columns:
        n = c.name.lower()
        if c.is_primary_key or c.is_identity or n.endswith(("id", "code", "key")):
            out.append(c.name)
    return out


def build_exact_profile_query(table: Table, columns: list | None = None) -> tuple:
    """Build the exact-aggregate query. Pure — returns (sql, plan).

    ``plan`` is a list of (column, kind, alias) so the caller can map result
    columns back. Returns ("", []) when there is nothing to profile.
    """
    cols = table.columns
    if columns is not None:
        wanted = {c.lower() for c in columns}
        cols = [c for c in cols if c.name.lower() in wanted]
    if not cols:
        return "", []

    select_parts = ["COUNT_BIG(*) AS __total"]
    plan = []
    for i, c in enumerate(cols):
        a_null = f"c{i}_nulls"
        select_parts.append(
            f"SUM(CASE WHEN [{c.name}] IS NULL THEN 1 ELSE 0 END) AS {a_null}"
        )
        plan.append((c, "nulls", a_null))
        if can_aggregate(c):
            a_d, a_min, a_max = f"c{i}_distinct", f"c{i}_min", f"c{i}_max"
            select_parts.append(f"COUNT_BIG(DISTINCT [{c.name}]) AS {a_d}")
            select_parts.append(f"MIN([{c.name}]) AS {a_min}")
            select_parts.append(f"MAX([{c.name}]) AS {a_max}")
            plan.append((c, "distinct", a_d))
            plan.append((c, "min", a_min))
            plan.append((c, "max", a_max))

    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM [{table.schema}].[{table.name}]"
    )
    return sql, plan


def apply_exact_results(table: Table, plan: list, result: dict, total_key: str = "__total") -> Table:
    """Apply an exact-query result row (alias -> value dict) to the table. Pure."""
    total = int(result.get(total_key) or 0)
    touched = set()
    for col, kind, alias in plan:
        val = result.get(alias)
        if kind == "nulls":
            col.profile_mode = "exact"
            col.sampled_rows = total  # exact => denominator is the full table
            col.null_count = int(val or 0)
            touched.add(col.name)
        elif kind == "distinct":
            col.distinct_count = int(val) if val is not None else None
        elif kind == "min":
            col.min_value = None if val is None else str(val)
        elif kind == "max":
            col.max_value = None if val is None else str(val)
    return table


def profile_table_exact(conn, table: Table, columns: list | None = None) -> Table:
    """Run exact aggregates over the whole table (optionally a column subset)."""
    sql, plan = build_exact_profile_query(table, columns)
    if not plan:
        return table
    cur = conn.cursor()
    cur.execute(sql)
    row = cur.fetchone()
    names = [d[0] for d in cur.description]
    result = dict(zip(names, row))
    return apply_exact_results(table, plan, result)


def profile_catalog_exact(
    conn, catalog: Catalog, limit: int = 25, keys_only: bool = True
) -> list:
    """Exact-profile the top ``limit`` tables.

    ``keys_only`` (default) profiles just key-like columns — cheap, and enough
    to confirm primary keys. Set it False to exact-profile every aggregatable
    column (heavier).
    """
    targets = select_tables_to_profile(catalog, limit=limit)
    done = []
    for t in targets:
        if t.row_count == 0:
            continue
        cols = key_like_columns(t) if keys_only else None
        profile_table_exact(conn, t, columns=cols)
        done.append(t)
    return done
