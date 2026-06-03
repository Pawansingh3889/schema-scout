"""Rank tables by real query activity.

Row count tells you what's *big*; query activity tells you what's *used* —
usually the better answer to "where should we focus". SQL Server records this
in Query Store (preferred) and, as a fallback, in the plan-cache DMVs. We pull
the query texts with their execution counts and match table names against
them.

``extract_query_activity`` touches the DB (needs VIEW SERVER STATE, or Query
Store enabled). ``score_usage`` is pure — given a list of (query_text, count)
it scores the catalog — so the matching logic is unit-tested without a DB.

Matching is by table-name token and is deliberately simple; treat the scores
as a ranking signal, not an exact count.
"""
from __future__ import annotations

import re

from schema_scout.model import Catalog

# Preferred: Query Store (persisted history, survives restarts).
_QUERY_STORE_SQL = """
SELECT qt.query_sql_text, SUM(rs.count_executions) AS execs
FROM sys.query_store_query_text qt
JOIN sys.query_store_query q ON q.query_text_id = qt.query_text_id
JOIN sys.query_store_plan p ON p.query_id = q.query_id
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
GROUP BY qt.query_sql_text
"""

# Fallback: plan cache (only what's currently cached, but always available).
_DMV_SQL = """
SELECT t.text AS query_sql_text, qs.execution_count AS execs
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) t
"""


def extract_query_activity(conn) -> list:
    """Return [(query_text, execution_count)] from Query Store or the DMVs."""
    cur = conn.cursor()
    try:
        cur.execute(_QUERY_STORE_SQL)
        rows = cur.fetchall()
        if rows:
            return [(r[0], int(r[1] or 0)) for r in rows]
    except Exception:
        pass  # Query Store off or no permission -> fall back
    cur2 = conn.cursor()
    cur2.execute(_DMV_SQL)
    return [(r[0], int(r[1] or 0)) for r in cur2.fetchall()]


def _table_pattern(name: str):
    # the name as a whole token, optionally bracketed; case-insensitive
    return re.compile(r"(?<![\w\[])\[?" + re.escape(name) + r"\]?(?![\w])", re.IGNORECASE)


def score_usage(catalog: Catalog, activity: list) -> dict:
    """Set ``usage_score`` / ``query_count`` on each table. Returns the scores."""
    patterns = [(t, _table_pattern(t.name)) for t in catalog.tables]
    scores = {t.qualified_name: 0 for t in catalog.tables}
    counts = {t.qualified_name: 0 for t in catalog.tables}

    for text, execs in activity:
        if not text:
            continue
        for t, pat in patterns:
            if pat.search(text):
                scores[t.qualified_name] += execs
                counts[t.qualified_name] += 1

    for t in catalog.tables:
        t.usage_score = float(scores[t.qualified_name])
        t.query_count = counts[t.qualified_name]
    return scores
