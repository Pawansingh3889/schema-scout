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

from schema_scout.model import Catalog, Table


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
