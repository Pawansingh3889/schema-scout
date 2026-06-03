"""Find join paths between tables.

"How do I get from customers to invoice_lines?" — breadth-first search over
the relationship graph (declared + inferred), returning the shortest chain of
joins. This is what makes a 147-table schema queryable, and it's the piece a
NL->SQL layer needs to build correct multi-table joins. Pure over the
in-memory catalog; unit-testable without a database.
"""
from __future__ import annotations

from collections import deque

from schema_scout.model import Catalog, ForeignKey


def _adjacency(catalog: Catalog) -> dict:
    adj: dict = {}
    for fk in catalog.relationships:
        a, b = fk.parent_qualified, fk.ref_qualified
        adj.setdefault(a, []).append((b, fk))
        adj.setdefault(b, []).append((a, fk))
    return adj


def _join_on(fk: ForeignKey) -> str:
    return (
        f"{fk.parent_schema}.{fk.parent_table}.{fk.parent_column} = "
        f"{fk.ref_schema}.{fk.ref_table}.{fk.ref_column}"
    )


def find_path(catalog: Catalog, src: str, dst: str) -> list | None:
    """Shortest join path from ``src`` to ``dst`` (qualified names).

    Returns a list of step dicts ({from, to, on, inferred}); an empty list if
    src == dst; or None if the two are not connected.
    """
    if src == dst:
        return []
    adj = _adjacency(catalog)
    if src not in adj or dst not in adj:
        return None

    prev: dict = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        if cur == dst:
            break
        for nbr, fk in adj.get(cur, []):
            if nbr not in prev:
                prev[nbr] = (cur, fk)
                q.append(nbr)

    if dst not in prev:
        return None

    steps = []
    node = dst
    while prev[node] is not None:
        cur, fk = prev[node]
        steps.append(
            {"from": cur, "to": node, "on": _join_on(fk), "inferred": fk.inferred}
        )
        node = cur
    steps.reverse()
    return steps


def path_to_text(steps: list | None, src: str = "", dst: str = "") -> str:
    """Human-readable rendering of a path returned by ``find_path``."""
    if steps is None:
        return f"No join path between {src} and {dst}."
    if not steps:
        return f"{src} and {dst} are the same table."
    lines = [f"{len(steps)} join(s):"]
    for s in steps:
        tag = " (inferred)" if s["inferred"] else ""
        lines.append(f"  {s['from']} -> {s['to']}  ON {s['on']}{tag}")
    return "\n".join(lines)
