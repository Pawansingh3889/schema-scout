"""On-prem AI descriptions via Ollama.

This is the differentiated layer: feed each table's structure + profile +
sample values to a *local* LLM and get back plain-English descriptions that
make the catalog searchable and feed a NL->SQL retriever. Local means no
schema or sample data leaves the machine — the whole point for regulated or
privacy-sensitive databases.

``requests`` and a running Ollama are only needed for ``describe_*``; prompt
building is pure and testable.
"""
from __future__ import annotations

import json

from schema_scout.model import Table

_SYSTEM = (
    "You are a data analyst documenting a database for other analysts. "
    "Be concise and factual. Do not invent columns or meanings you cannot "
    "infer from the names, types and sample values given."
)


def build_describe_prompt(table: Table, max_cols: int = 60) -> str:
    """Build a prompt asking for a table description + per-column one-liners.

    Asks for strict JSON back so the result is machine-parseable.
    """
    lines = [
        f"Table: {table.qualified_name}",
        f"Role (heuristic): {table.kind}",
        f"Approx rows: {table.row_count:,}",
        f"Primary key: {', '.join(table.primary_key) or 'none declared'}",
        "",
        "Columns (name | type | sample values):",
    ]
    for c in table.columns[:max_cols]:
        samples = ", ".join(c.sample_values[:5]) if c.sample_values else ""
        pk = " [PK]" if c.is_primary_key else ""
        lines.append(f"- {c.name} | {c.data_type}{pk} | {samples}")
    if table.foreign_keys:
        lines.append("")
        lines.append("Relationships:")
        for fk in table.foreign_keys:
            lines.append(
                f"- {fk.parent_column} -> {fk.ref_table}.{fk.ref_column}"
            )
    lines.append("")
    lines.append(
        "Respond with JSON only, no prose, in exactly this shape:\n"
        '{"table": "one sentence on what this table holds", '
        '"columns": {"<column_name>": "short meaning", ...}}'
    )
    return "\n".join(lines)


def describe_table(
    table: Table,
    model: str = "qwen3:14b",
    host: str = "http://localhost:11434",
    timeout: int = 120,
) -> dict:
    """Call a local Ollama model and apply the descriptions to ``table``.

    Returns the parsed dict. On any failure returns {} and leaves the table
    untouched, so a bad/absent model never breaks a catalog run.
    """
    import requests

    prompt = build_describe_prompt(table)
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "system": _SYSTEM,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        parsed = json.loads(raw)
    except Exception:
        return {}

    if isinstance(parsed.get("table"), str):
        table.description = parsed["table"].strip()
    col_desc = parsed.get("columns", {})
    if isinstance(col_desc, dict):
        for c in table.columns:
            d = col_desc.get(c.name)
            if isinstance(d, str) and d.strip():
                c.description = d.strip()
    return parsed
