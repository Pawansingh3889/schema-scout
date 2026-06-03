"""Turn inferred relationships into something a DBA or dbt project can use.

Inference is only useful if it produces an actionable artifact. This emits:

- a reviewable T-SQL script of suggested foreign-key constraints (WITH NOCHECK
  so it doesn't validate existing rows until you say so), and
- a dbt ``schema.yml`` with ``relationships`` tests for each foreign key.

Pure string builders over the catalog; unit-testable without a database.
"""
from __future__ import annotations

from schema_scout.model import Catalog


def to_sql_constraints(catalog: Catalog, only_inferred: bool = True) -> str:
    """Suggested FK constraints as a reviewable T-SQL script."""
    lines = [
        "-- Suggested foreign-key constraints from schema-scout.",
        "-- REVIEW before running. WITH NOCHECK adds the constraint without",
        "-- validating existing rows; drop NOCHECK to enforce against current data.",
        "",
    ]
    n = 0
    for fk in catalog.relationships:
        if only_inferred and not fk.inferred:
            continue
        cname = f"FK_{fk.parent_table}_{fk.parent_column}__{fk.ref_table}".replace(" ", "_")
        note = (
            f"  -- inferred {fk.confidence:.0%}: {fk.reason}"
            if fk.inferred
            else "  -- declared"
        )
        lines.append(f"ALTER TABLE [{fk.parent_schema}].[{fk.parent_table}] WITH NOCHECK")
        lines.append(f"  ADD CONSTRAINT [{cname}] FOREIGN KEY ([{fk.parent_column}])")
        lines.append(
            f"  REFERENCES [{fk.ref_schema}].[{fk.ref_table}] ([{fk.ref_column}]);{note}"
        )
        lines.append("")
        n += 1
    if n == 0:
        lines.append("-- (no relationships to suggest)")
    return "\n".join(lines) + "\n"


def to_dbt_relationships(catalog: Catalog) -> str:
    """A dbt sources schema.yml carrying relationships tests for every FK."""
    lines = ["version: 2", "", "sources:", "  - name: schema_scout", "    tables:"]
    any_table = False
    for t in catalog.tables:
        if not t.foreign_keys:
            continue
        any_table = True
        lines.append(f"      - name: {t.name}")
        lines.append("        columns:")
        for fk in t.foreign_keys:
            lines.append(f"          - name: {fk.parent_column}")
            lines.append("            tests:")
            lines.append("              - relationships:")
            lines.append(f"                  to: source('schema_scout', '{fk.ref_table}')")
            lines.append(f"                  field: {fk.ref_column}")
    if not any_table:
        lines.append("      []")
    return "\n".join(lines) + "\n"
