"""Render the catalog as compact context for an LLM / AI agent.

The "data stack is for agents" shift means a schema map's most useful consumer
is increasingly an LLM doing natural-language-to-SQL, not a person reading a
diagram. This emits the catalog as a compact, structured context an agent can
load: each table's role and description, its columns (with PK / FK / PII
flags), and explicit join keys so the model can build correct multi-table
queries. Pure function over the in-memory catalog.

This is an agent *context file*, not an MCP server — MCP is a protocol, and a
live MCP server is a separate, larger piece (see ROADMAP.md). Kept lean on
purpose: agents pay per token, so profile noise is left out and optional keys
appear only when they carry a value.
"""
from __future__ import annotations

import json

from schema_scout.model import Catalog, Table


def _table_context(t: Table) -> dict:
    fk_map = {
        fk.parent_column.lower(): f"{fk.ref_schema}.{fk.ref_table}.{fk.ref_column}"
        for fk in t.foreign_keys
    }

    cols = []
    for c in t.columns:
        col: dict = {"name": c.name, "type": c.data_type}
        if c.is_primary_key:
            col["pk"] = True
        fk_target = fk_map.get(c.name.lower())
        if fk_target:
            col["fk"] = fk_target
        if c.is_pii:
            col["pii"] = c.pii_kind
        if c.description:
            col["description"] = c.description
        if c.sample_values:
            col["examples"] = c.sample_values[:3]
        cols.append(col)

    joins = [
        {
            "to": fk.ref_qualified,
            "on": (
                f"{fk.parent_table}.{fk.parent_column} = "
                f"{fk.ref_table}.{fk.ref_column}"
            ),
            "inferred": fk.inferred,
            "confidence": round(fk.confidence, 2),
        }
        for fk in t.foreign_keys
    ]

    ctx: dict = {"name": t.qualified_name}
    if t.subject_area:
        ctx["domain"] = t.subject_area
    ctx["role"] = t.kind  # fact / dimension / bridge / reference
    if t.description:
        ctx["description"] = t.description
    ctx["row_count"] = t.row_count
    if t.primary_key:
        ctx["primary_key"] = t.primary_key
    ctx["columns"] = cols
    ctx["joins"] = joins
    return ctx


def to_agent_context(catalog: Catalog) -> dict:
    """A compact, agent-loadable description of the whole schema."""
    pii_cols = sum(1 for t in catalog.tables for c in t.columns if c.is_pii)
    domains = sorted({t.subject_area for t in catalog.tables if t.subject_area})
    return {
        "format": "schema-scout/agent-context/1",
        "summary": {
            "tables": len(catalog.tables),
            "relationships": len(catalog.relationships),
            "domains": len(domains),
            "pii_columns": pii_cols,
        },
        "domains": domains,
        "tables": [_table_context(t) for t in catalog.tables],
    }


def to_agent_json(catalog: Catalog, indent: int = 2) -> str:
    return json.dumps(to_agent_context(catalog), indent=indent, default=str)
