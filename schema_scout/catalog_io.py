"""Load a previously rendered ``catalog.json`` back into the model.

``render.to_dict`` writes the catalog out; this reads it back so the pure
functions (join-path, agent context, etc.) and the MCP server can work from a
saved catalog without touching the database again. The round-trip keeps the
fields those consumers need; a few profile-only fields (e.g. exact null counts)
aren't restored because they aren't in the JSON.
"""
from __future__ import annotations

import json

from schema_scout.model import Catalog, Column, ForeignKey, Table


def catalog_from_dict(data: dict) -> Catalog:
    tables = []
    relationships = []
    for t in data.get("tables", []):
        schema = t["schema"]
        name = t["name"]
        tb = Table(
            schema=schema,
            name=name,
            row_count=int(t.get("row_count") or 0),
            primary_key=list(t.get("primary_key") or []),
            kind=t.get("kind", "unknown"),
            subject_area=t.get("subject_area"),
            description=t.get("description"),
            usage_score=float(t.get("usage_score") or 0.0),
            query_count=int(t.get("query_count") or 0),
        )
        for c in t.get("columns", []):
            col = Column(
                schema=schema,
                table=name,
                name=c["name"],
                ordinal=0,
                data_type=c.get("data_type", ""),
                is_nullable=bool(c.get("nullable", True)),
                is_primary_key=bool(c.get("primary_key", False)),
                is_identity=bool(c.get("identity", False)),
                profile_mode=c.get("profile_mode"),
                sampled_rows=c.get("sampled_rows"),
                distinct_count=c.get("distinct_count"),
                min_value=c.get("min"),
                max_value=c.get("max"),
                sample_values=list(c.get("sample_values") or []),
                description=c.get("description"),
            )
            pii = c.get("pii")
            if pii:
                col.is_pii = True
                col.pii_kind = pii
            tb.columns.append(col)
        for fk in t.get("foreign_keys", []):
            pf = fk["from"].split(".")
            rt = fk["to"].split(".")
            f = ForeignKey(
                name=fk.get("name", ""),
                parent_schema=pf[0],
                parent_table=pf[1],
                parent_column=pf[2],
                ref_schema=rt[0],
                ref_table=rt[1],
                ref_column=rt[2],
                inferred=bool(fk.get("inferred", False)),
                confidence=float(fk.get("confidence", 1.0)),
                reason=fk.get("reason", "declared"),
            )
            tb.foreign_keys.append(f)
            relationships.append(f)
        tables.append(tb)
    return Catalog(tables=tables, relationships=relationships)


def load_catalog(path: str) -> Catalog:
    with open(path, encoding="utf-8") as f:
        return catalog_from_dict(json.load(f))
