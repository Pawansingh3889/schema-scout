"""Infer undeclared foreign keys.

Legacy and ERP schemas frequently omit declared FK constraints, so the
relationship map is mostly invisible to the catalog. This module guesses the
missing edges from naming/typing conventions, then offers an optional
value-inclusion check against the live DB to turn a guess into near-certainty.

Pure inference (``infer_relationships``) takes a Catalog and returns
candidates — no DB needed, fully unit-testable. ``validate_inclusion`` is the
separate, DB-touching confirmation step.
"""
from __future__ import annotations

import re

from schema_scout.model import Catalog, ForeignKey, Table

_ID_SUFFIX = re.compile(r"^(?P<base>.*?)[_]?id$", re.IGNORECASE)


def singularize(name: str) -> str:
    """Crude English singularizer — enough for table-name matching."""
    n = name.lower()
    if n.endswith("ies") and len(n) > 3:
        return n[:-3] + "y"
    if n.endswith("ses") or n.endswith("xes") or n.endswith("ches") or n.endswith("shes"):
        return n[:-2]
    if n.endswith("s") and not n.endswith(("ss", "us", "is")):
        return n[:-1]
    return n


def _name_variants(base: str) -> set:
    base = base.lower().strip("_")
    return {base, singularize(base), base + "s", base + "es", singularize(base) + "s"}


def _build_name_index(tables: list) -> dict:
    """Map every plausible spelling of a table name to the Table."""
    index: dict = {}
    for t in tables:
        for variant in _name_variants(t.name) | {t.name.lower()}:
            index.setdefault(variant, t)
    return index


def _types_compatible(a: str, b: str) -> bool:
    def fam(t: str) -> str:
        t = t.lower()
        if "int" in t:
            return "int"
        if any(k in t for k in ("char", "text")):
            return "str"
        if "unique" in t or "guid" in t:
            return "guid"
        if any(k in t for k in ("decimal", "numeric", "money")):
            return "num"
        return t

    return fam(a) == fam(b)


def infer_relationships(catalog: Catalog) -> list:
    """Return inferred ForeignKey candidates not already declared.

    Heuristic: a column ``<base>_id`` / ``<base>id`` that is *not* its own
    table's PK points at a table whose name matches ``<base>`` and which has a
    single-column primary key. Type agreement raises confidence.
    """
    tables = catalog.tables
    name_index = _build_name_index(tables)

    declared = {
        (fk.parent_schema.lower(), fk.parent_table.lower(), fk.parent_column.lower())
        for fk in catalog.relationships
        if not fk.inferred
    }

    candidates = []
    for t in tables:
        for c in t.columns:
            if c.is_primary_key:
                continue
            m = _ID_SUFFIX.match(c.name)
            if not m:
                continue
            base = m.group("base").strip("_")
            if not base:
                continue  # a bare "id" column references nothing

            target = None
            for variant in _name_variants(base):
                cand = name_index.get(variant)
                if cand and cand.qualified_name != t.qualified_name:
                    target = cand
                    break
            if target is None or len(target.primary_key) != 1:
                continue

            key = (t.schema.lower(), t.name.lower(), c.name.lower())
            if key in declared:
                continue  # already a real FK

            ref_col = target.primary_key[0]
            ref_column = target.column(ref_col)
            type_ok = ref_column is not None and _types_compatible(
                c.data_type, ref_column.data_type
            )
            confidence = 0.8 if type_ok else 0.5
            reason = (
                f"name '{c.name}' -> {target.name}.{ref_col}"
                f"{'' if type_ok else ' (type mismatch)'}"
            )
            candidates.append(
                ForeignKey(
                    name=f"inferred_{t.name}_{c.name}",
                    parent_schema=t.schema,
                    parent_table=t.name,
                    parent_column=c.name,
                    ref_schema=target.schema,
                    ref_table=target.name,
                    ref_column=ref_col,
                    inferred=True,
                    confidence=confidence,
                    reason=reason,
                )
            )
    return candidates


def validate_inclusion(conn, fk: ForeignKey, sample_size: int = 100000) -> float:
    """Confirm an inferred FK by checking value inclusion on the live DB.

    Returns the fraction of non-null parent values that exist in the
    referenced column (1.0 = every value matches). A high ratio is strong
    evidence the relationship is real; mutate ``fk.confidence`` from the
    caller based on the result.
    """
    cur = conn.cursor()
    p = f"[{fk.parent_schema}].[{fk.parent_table}]"
    r = f"[{fk.ref_schema}].[{fk.ref_table}]"
    sql = f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN EXISTS (
                       SELECT 1 FROM {r} ref
                       WHERE ref.[{fk.ref_column}] = p.[{fk.parent_column}]
                   ) THEN 1 ELSE 0 END) AS matched
        FROM (
            SELECT TOP ({int(sample_size)}) [{fk.parent_column}]
            FROM {p}
            WHERE [{fk.parent_column}] IS NOT NULL
        ) p
    """
    cur.execute(sql)
    total, matched = cur.fetchone()
    if not total:
        return 0.0
    return float(matched or 0) / float(total)


def merge_inferred(catalog: Catalog, candidates: list, min_confidence: float = 0.5) -> int:
    """Add accepted candidates to the catalog. Returns how many were added."""
    added = 0
    for fk in candidates:
        if fk.confidence < min_confidence:
            continue
        catalog.relationships.append(fk)
        t = catalog.get(fk.parent_schema, fk.parent_table)
        if t is not None:
            t.foreign_keys.append(fk)
        added += 1
    return added
