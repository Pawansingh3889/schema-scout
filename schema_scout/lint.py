"""Schema health checks (lint).

Surfaces design problems and data-quality smells a decision-maker cares about
because they mark risk and modelling debt: tables with no primary key, orphan
tables with no relationships, columns that are entirely null / constant /
mostly null, and unexpectedly unique columns. Pure over the in-memory
catalog, so it unit-tests without a database.

Data-quality findings depend on the profile having been run; structural ones
(no PK, orphan) do not.
"""
from __future__ import annotations

from schema_scout.model import Catalog, Table

HIGH_NULL_PCT = 50.0
WIDE_TABLE_COLS = 40
_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _finding(severity: str, code: str, table: Table, column, message: str) -> dict:
    return {
        "severity": severity,
        "code": code,
        "table": table.qualified_name,
        "domain": table.subject_area or "Ungrouped",
        "column": column,
        "message": message,
    }


def lint_catalog(
    catalog: Catalog,
    high_null_pct: float = HIGH_NULL_PCT,
    wide_cols: int = WIDE_TABLE_COLS,
) -> list:
    """Return a list of findings, most severe first."""
    referenced = {fk.ref_qualified for fk in catalog.relationships}
    findings = []

    for t in catalog.tables:
        has_rel = bool(t.foreign_keys) or t.qualified_name in referenced

        if not t.primary_key:
            findings.append(
                _finding("high", "no_primary_key", t, None,
                         f"{t.qualified_name} has no primary key")
            )
        if not has_rel and t.row_count > 0:
            findings.append(
                _finding("medium", "orphan_table", t, None,
                         f"{t.qualified_name} has no relationships (orphan)")
            )
        if t.column_count >= wide_cols:
            findings.append(
                _finding("low", "wide_table", t, None,
                         f"{t.qualified_name} is wide ({t.column_count} columns)")
            )

        for c in t.columns:
            if not c.sampled_rows:
                continue
            if c.null_count == c.sampled_rows:
                findings.append(
                    _finding("high", "all_null", t, c.name,
                             f"{c.qualified_table}.{c.name} is entirely NULL in the sample")
                )
            elif c.distinct_count == 1:
                findings.append(
                    _finding("medium", "constant", t, c.name,
                             f"{c.qualified_table}.{c.name} holds a single constant value")
                )
            elif c.null_pct is not None and c.null_pct >= high_null_pct:
                findings.append(
                    _finding("medium", "high_null", t, c.name,
                             f"{c.qualified_table}.{c.name} is {c.null_pct}% NULL")
                )
            if (
                not c.is_primary_key
                and not c.is_identity
                and c.distinct_count == c.sampled_rows
                and c.sampled_rows > 0
            ):
                findings.append(
                    _finding("low", "unique_candidate", t, c.name,
                             f"{c.qualified_table}.{c.name} is unique in the sample "
                             f"(candidate key)")
                )

    findings.sort(key=lambda f: (_SEV_ORDER[f["severity"]], f["table"]))
    return findings


def summarize_lint(findings: list) -> dict:
    out = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        out[f["severity"]] = out.get(f["severity"], 0) + 1
    return out
