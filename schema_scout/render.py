"""Render a catalog to JSON, Markdown, and a Mermaid ER diagram.

JSON is the machine-readable artifact (and the shape OpsMind's retriever can
index). Markdown is the human catalog. Mermaid is the visual map — with 150
tables the full diagram is unreadable, so ``to_mermaid`` can be scoped to a
subject area or a subset of tables.
"""
from __future__ import annotations

import json
import re

from schema_scout.model import Catalog, Column, ForeignKey, Table


def _col_json(c: Column) -> dict:
    return {
        "name": c.name,
        "data_type": c.data_type,
        "nullable": c.is_nullable,
        "primary_key": c.is_primary_key,
        "identity": c.is_identity,
        "null_pct": c.null_pct,
        "distinct_count": c.distinct_count,
        "sampled_rows": c.sampled_rows,
        "min": c.min_value,
        "max": c.max_value,
        "sample_values": c.sample_values,
        "pii": c.pii_kind if c.is_pii else None,
        "description": c.description,
    }


def _fk_json(fk: ForeignKey) -> dict:
    return {
        "name": fk.name,
        "from": f"{fk.parent_schema}.{fk.parent_table}.{fk.parent_column}",
        "to": f"{fk.ref_schema}.{fk.ref_table}.{fk.ref_column}",
        "inferred": fk.inferred,
        "confidence": round(fk.confidence, 2),
        "reason": fk.reason,
    }


def _table_json(t: Table) -> dict:
    return {
        "schema": t.schema,
        "name": t.name,
        "qualified_name": t.qualified_name,
        "kind": t.kind,
        "subject_area": t.subject_area,
        "row_count": t.row_count,
        "primary_key": t.primary_key,
        "description": t.description,
        "columns": [_col_json(c) for c in t.columns],
        "foreign_keys": [_fk_json(fk) for fk in t.foreign_keys],
    }


def to_dict(catalog: Catalog) -> dict:
    return {
        "table_count": len(catalog.tables),
        "relationship_count": len(catalog.relationships),
        "tables": [_table_json(t) for t in catalog.tables],
    }


def to_json(catalog: Catalog, indent: int = 2) -> str:
    return json.dumps(to_dict(catalog), indent=indent, default=str)


# --- Markdown ------------------------------------------------------------

def to_markdown(catalog: Catalog) -> str:
    tables = sorted(catalog.tables, key=lambda t: t.row_count, reverse=True)
    n_inf = sum(1 for fk in catalog.relationships if fk.inferred)
    pii_cols = [
        (t.qualified_name, c.name, c.pii_kind)
        for t in catalog.tables
        for c in t.columns
        if c.is_pii
    ]

    out = ["# Data catalog", ""]
    out.append(
        f"{len(catalog.tables)} tables, {len(catalog.relationships)} "
        f"relationships ({n_inf} inferred). "
        f"{len(pii_cols)} columns flagged as potential PII."
    )
    out.append("")

    # overview
    out.append("## Tables by size")
    out.append("")
    out.append("| Table | Kind | Rows | Cols | FKs | PK |")
    out.append("|---|---|--:|--:|--:|---|")
    for t in tables:
        out.append(
            f"| `{t.qualified_name}` | {t.kind} | {t.row_count:,} | "
            f"{t.column_count} | {len(t.foreign_keys)} | "
            f"{', '.join(t.primary_key) or '—'} |"
        )
    out.append("")

    if pii_cols:
        out.append("## ⚠️ Potential PII")
        out.append("")
        out.append("| Table | Column | Kind |")
        out.append("|---|---|---|")
        for tbl, col, kind in pii_cols:
            out.append(f"| `{tbl}` | `{col}` | {kind} |")
        out.append("")

    # per-table detail
    out.append("## Table detail")
    out.append("")
    for t in tables:
        out.append(f"### `{t.qualified_name}`  ·  {t.kind}  ·  {t.row_count:,} rows")
        if t.description:
            out.append("")
            out.append(t.description)
        out.append("")
        out.append("| Column | Type | Null | Null% | Distinct | PII | Notes |")
        out.append("|---|---|---|--:|--:|---|---|")
        for c in t.columns:
            flags = []
            if c.is_primary_key:
                flags.append("PK")
            if c.is_identity:
                flags.append("identity")
            null_pct = "" if c.null_pct is None else f"{c.null_pct}%"
            distinct = "" if c.distinct_count is None else f"{c.distinct_count:,}"
            out.append(
                f"| `{c.name}` | {c.data_type} | "
                f"{'yes' if c.is_nullable else 'no'} | {null_pct} | {distinct} | "
                f"{c.pii_kind or ''} | {' '.join(flags)} |"
            )
        if t.foreign_keys:
            out.append("")
            out.append("**Relationships:**")
            for fk in t.foreign_keys:
                tag = (
                    f"_inferred {fk.confidence:.0%}_"
                    if fk.inferred
                    else "declared"
                )
                out.append(
                    f"- `{fk.parent_column}` → "
                    f"`{fk.ref_schema}.{fk.ref_table}.{fk.ref_column}` ({tag})"
                )
        out.append("")
    return "\n".join(out)


# --- Mermaid ER diagram --------------------------------------------------

def _ent(name: str) -> str:
    """Mermaid entity id: alnum + underscore only."""
    return re.sub(r"[^0-9A-Za-z_]", "_", name)


def to_mermaid(catalog: Catalog, tables: list | None = None, max_tables: int = 40) -> str:
    """Render an ``erDiagram``. Scope with ``tables`` (qualified names) or it
    falls back to the ``max_tables`` largest tables so the diagram stays
    legible on a big schema.
    """
    if tables is not None:
        wanted = set(tables)
        chosen = [t for t in catalog.tables if t.qualified_name in wanted]
    else:
        chosen = sorted(catalog.tables, key=lambda t: t.row_count, reverse=True)[:max_tables]

    chosen_names = {t.qualified_name for t in chosen}
    lines = ["erDiagram"]

    for t in chosen:
        ent = _ent(t.qualified_name)
        lines.append(f"    {ent} {{")
        for c in t.columns:
            key = "PK" if c.is_primary_key else ("FK" if any(
                fk.parent_column == c.name for fk in t.foreign_keys
            ) else "")
            typ = _ent(c.data_type)
            lines.append(f"        {typ} {c.name} {key}".rstrip())
        lines.append("    }")

    for fk in catalog.relationships:
        if fk.parent_qualified in chosen_names and fk.ref_qualified in chosen_names:
            a = _ent(fk.ref_qualified)
            b = _ent(fk.parent_qualified)
            label = "inferred" if fk.inferred else fk.parent_column
            # one (ref) to many (parent)
            lines.append(f'    {a} ||--o{{ {b} : "{label}"')

    return "\n".join(lines)
