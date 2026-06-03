"""Group tables into subject areas (domains).

A decision-maker thinks in domains ("Sales", "Production"), not in 147
individual tables. This module assigns each table a subject area so the
catalog and the dashboard can roll metrics up to that level.

Two strategies, picked automatically:

- **prefix** — group by the first token of the table name. Works well for
  ERP/module-prefixed schemas (``SalesOrder``, ``SalesOrderLine``,
  ``ProductionRun`` or ``sal_order``, ``prd_run``).
- **components** — connected components of the foreign-key graph (declared +
  inferred), named after the largest table in each. Used when names don't
  share meaningful prefixes.

Pure functions over the in-memory catalog — no DB, fully unit-testable.
It's a heuristic starting point a human can rename or merge, not a verdict.
"""
from __future__ import annotations

import re
from collections import defaultdict

from schema_scout.model import Catalog

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def first_token(name: str) -> str:
    """First word of a table name, handling snake_case and CamelCase."""
    if "_" in name:
        head = name.split("_", 1)[0]
        return head.lower() or name.lower()
    parts = _CAMEL.findall(name)
    return parts[0].lower() if parts else name.lower()


def humanize(name: str) -> str:
    return name.replace("_", " ").strip().title() or name


def _prefix_assignment(catalog: Catalog) -> dict:
    assign = {}
    for t in catalog.tables:
        dom = humanize(first_token(t.name))
        t.subject_area = dom
        assign[t.qualified_name] = dom
    return assign


def _component_assignment(catalog: Catalog) -> dict:
    parent = {t.qualified_name: t.qualified_name for t in catalog.tables}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    names = set(parent)
    for fk in catalog.relationships:
        if fk.parent_qualified in names and fk.ref_qualified in names:
            union(fk.parent_qualified, fk.ref_qualified)

    comps = defaultdict(list)
    for t in catalog.tables:
        comps[find(t.qualified_name)].append(t)

    assign = {}
    for members in comps.values():
        hub = max(members, key=lambda t: (t.row_count, t.column_count))
        dom = humanize(hub.name)
        for t in members:
            t.subject_area = dom
            assign[t.qualified_name] = dom
    return assign


def infer_domains(catalog: Catalog, strategy: str = "auto") -> dict:
    """Assign ``subject_area`` to every table. Returns {qualified_name: domain}."""
    if not catalog.tables:
        return {}
    if strategy == "auto":
        tokens = {first_token(t.name) for t in catalog.tables}
        # prefixes are "meaningful" when tables share them (few distinct tokens
        # relative to table count)
        meaningful = len(tokens) <= max(2, len(catalog.tables) * 0.6)
        strategy = "prefix" if meaningful else "components"
    if strategy == "prefix":
        return _prefix_assignment(catalog)
    return _component_assignment(catalog)


def summarize_domains(catalog: Catalog) -> list:
    """Per-domain rollup for the dashboard. Sorted by row volume."""
    doms: dict = defaultdict(
        lambda: {
            "name": "",
            "tables": 0,
            "rows": 0,
            "columns": 0,
            "pii": 0,
            "inferred_fks": 0,
            "declared_fks": 0,
            "queries": 0,
            "kinds": defaultdict(int),
        }
    )
    for t in catalog.tables:
        key = t.subject_area or "Ungrouped"
        d = doms[key]
        d["name"] = key
        d["tables"] += 1
        d["rows"] += t.row_count
        d["columns"] += t.column_count
        d["queries"] += t.query_count
        d["kinds"][t.kind] += 1
        for c in t.columns:
            if c.is_pii:
                d["pii"] += 1
        for fk in t.foreign_keys:
            if fk.inferred:
                d["inferred_fks"] += 1
            else:
                d["declared_fks"] += 1

    out = []
    for d in doms.values():
        d["kinds"] = dict(d["kinds"])
        out.append(d)
    out.sort(key=lambda x: x["rows"], reverse=True)
    return out
