"""Classify tables (fact / dimension / bridge / reference) and flag PII.

Pure functions over the in-memory catalog, so they unit-test without a DB.
The classification is a heuristic starting point for a human to confirm, not
a verdict — same correlate-don't-conclude discipline used elsewhere.
"""
from __future__ import annotations

import re
import statistics

from schema_scout.model import Catalog, Column, Table

# --- PII detection -------------------------------------------------------

_PII_NAME_PATTERNS = {
    "email": r"e[-_]?mail",
    "phone": r"(phone|mobile|telephone|fax)",
    "person_name": r"(first[_ ]?name|last[_ ]?name|surname|forename|full[_ ]?name)",
    "address": r"(address|street|postcode|post[_ ]?code|zip|city|county)",
    "dob": r"(date[_ ]?of[_ ]?birth|dob|birth[_ ]?date)",
    "national_id": r"(ni[_ ]?number|national[_ ]?insurance|ssn|passport|nino)",
    "bank": r"(iban|sort[_ ]?code|account[_ ]?number|card[_ ]?number)",
}
_PII_NAME_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _PII_NAME_PATTERNS.items()}

_EMAIL_VALUE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def detect_pii(column: Column) -> tuple:
    """Return (is_pii, kind) for a column, by name then by sample values."""
    for kind, rx in _PII_NAME_RE.items():
        if rx.search(column.name):
            return True, kind
    # value-based fallback: emails are unmistakable
    for v in column.sample_values:
        if _EMAIL_VALUE_RE.match(str(v)):
            return True, "email"
    return False, None


def annotate_pii(catalog: Catalog) -> int:
    flagged = 0
    for t in catalog.tables:
        for c in t.columns:
            is_pii, kind = detect_pii(c)
            c.is_pii = is_pii
            c.pii_kind = kind
            if is_pii:
                flagged += 1
    return flagged


# --- PK candidates -------------------------------------------------------

def pk_candidates(table: Table) -> list:
    """Columns that look like a unique key from the sample (unique + no nulls).

    Useful where no PK is declared. Sample-based, so treat as a hint.
    """
    out = []
    for c in table.columns:
        if c.sampled_rows and c.sampled_rows > 0:
            if c.null_count == 0 and c.distinct_count == c.sampled_rows:
                out.append(c.name)
    return out


# --- table classification ------------------------------------------------

def _fk_columns(table: Table) -> set:
    return {fk.parent_column.lower() for fk in table.foreign_keys}


def classify_table(table: Table, median_rows: float, ref_count: int) -> str:
    """Heuristic table role.

    - bridge: ~2 FKs and most columns are keys (a junction table)
    - fact: many FKs + numeric measures + above-median row count
    - dimension: referenced by others and descriptive / smaller
    - reference: tiny lookup table
    - unknown: doesn't fit
    """
    fk_cols = _fk_columns(table)
    n_fk = len(fk_cols)
    n_cols = max(table.column_count, 1)
    numeric_measures = [
        c
        for c in table.columns
        if c.is_numeric and not c.is_primary_key and c.name.lower() not in fk_cols
    ]

    # bridge / junction: a composite key (or 2+ FKs) and almost nothing else.
    # Composite-PK detection works even when FK constraints were never
    # declared, which is the common case in legacy schemas.
    non_key_cols = [
        c
        for c in table.columns
        if not c.is_primary_key and c.name.lower() not in fk_cols
    ]
    if (len(table.primary_key) >= 2 or n_fk >= 2) and len(non_key_cols) <= 1:
        return "bridge"

    # fact: transactional — several FKs, real measures, plenty of rows
    if n_fk >= 2 and numeric_measures and table.row_count >= median_rows:
        return "fact"

    # reference: small lookup, referenced by others
    if table.row_count <= max(median_rows * 0.1, 50) and ref_count > 0:
        return "reference"

    # dimension: referenced by others, descriptive
    if ref_count > 0:
        return "dimension"

    # a fact-shaped table nobody references yet
    if n_fk >= 2 and numeric_measures:
        return "fact"

    return "unknown"


def classify_catalog(catalog: Catalog) -> dict:
    """Classify every table in place. Returns a {kind: count} summary."""
    rows = [t.row_count for t in catalog.tables if t.row_count > 0]
    median_rows = statistics.median(rows) if rows else 0.0

    ref_counts: dict = {}
    for fk in catalog.relationships:
        ref_counts[fk.ref_qualified] = ref_counts.get(fk.ref_qualified, 0) + 1

    summary: dict = {}
    for t in catalog.tables:
        t.kind = classify_table(t, median_rows, ref_counts.get(t.qualified_name, 0))
        summary[t.kind] = summary.get(t.kind, 0) + 1
    return summary
