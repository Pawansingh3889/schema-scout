"""Score how ready a schema is for AI / natural-language-to-SQL.

An agent can only work with a schema it can understand and join. This turns
the catalog into a single 0-100 readiness score plus a breakdown, so a team
can see *what* to fix to make their data usable by an LLM:

- keys          — tables that have a primary key (joins need them)
- relationships — tables connected to at least one other (isolated tables
                  can't be reasoned about together)
- documentation — tables with a description (the semantic context an agent needs)
- cleanliness   — freedom from structural / data-quality problems

Pure function over the in-memory catalog. ``findings`` is optional; if not
given, the health checks are run.
"""
from __future__ import annotations

from schema_scout.model import Catalog

WEIGHTS = {
    "keys": 0.25,
    "relationships": 0.30,
    "documentation": 0.25,
    "cleanliness": 0.20,
}


def _pct(n: int, total: int) -> float:
    return 100.0 if total == 0 else round(100.0 * n / total, 1)


def _grade(score: float) -> tuple:
    if score >= 90:
        return "A", "Excellent"
    if score >= 75:
        return "B", "Good"
    if score >= 60:
        return "C", "Fair"
    if score >= 40:
        return "D", "Poor"
    return "F", "Not ready"


def compute_readiness(catalog: Catalog, findings: list | None = None) -> dict:
    if findings is None:
        from schema_scout import lint

        findings = lint.lint_catalog(catalog)

    tables = catalog.tables
    n = len(tables)
    referenced = {fk.ref_qualified for fk in catalog.relationships}

    with_pk = sum(1 for t in tables if t.primary_key)
    connected = sum(
        1 for t in tables if t.foreign_keys or t.qualified_name in referenced
    )
    documented = sum(1 for t in tables if t.description)
    problem_tables = {
        f["table"] for f in findings if f["severity"] in ("high", "medium")
    }
    clean = sum(1 for t in tables if t.qualified_name not in problem_tables)

    components = {
        "keys": _pct(with_pk, n),
        "relationships": _pct(connected, n),
        "documentation": _pct(documented, n),
        "cleanliness": _pct(clean, n),
    }
    score = round(sum(components[k] * WEIGHTS[k] for k in WEIGHTS), 1)
    letter, label = _grade(score)

    recommendations = []
    if n - with_pk:
        recommendations.append(f"{n - with_pk} table(s) have no primary key")
    if n - connected:
        recommendations.append(
            f"{n - connected} table(s) aren't connected to anything"
        )
    if n - documented:
        recommendations.append(
            f"{n - documented} table(s) have no description "
            f"(run --describe to add AI context)"
        )
    high = sum(1 for f in findings if f["severity"] == "high")
    if high:
        recommendations.append(f"{high} high-severity health issue(s) to resolve")

    return {
        "score": score,
        "grade": letter,
        "label": label,
        "components": components,
        "weights": WEIGHTS,
        "recommendations": recommendations,
    }
