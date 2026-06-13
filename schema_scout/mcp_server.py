"""An MCP server that lets an AI agent query a schema-scout catalog live.

This is the agentic-native piece: instead of stuffing 150 tables into a prompt,
an agent connects over the Model Context Protocol and asks for exactly what it
needs — which tables exist, how two of them join, what a table's columns and
PII look like, and the compact context for the ones relevant to a question.

It serves a previously generated ``catalog.json`` (so it's read-only and runs
fully on-prem; nothing touches the database at serve time). The tool logic
lives in plain functions (``tool_*``) so it's unit-testable without the ``mcp``
package installed; ``main`` wires them into a FastMCP server.

Run:  schema-scout-mcp --catalog out/catalog.json
"""
from __future__ import annotations

from schema_scout import agentcontext, domains, paths
from schema_scout.catalog_io import load_catalog
from schema_scout.model import Catalog


def tool_list_domains(catalog: Catalog) -> list:
    """Subject areas with their table/row/PII rollups."""
    return domains.summarize_domains(catalog)


def tool_list_tables(catalog: Catalog, domain: str | None = None, kind: str | None = None) -> list:
    """Tables, optionally filtered by domain or kind, largest first."""
    out = []
    for t in sorted(catalog.tables, key=lambda x: x.row_count, reverse=True):
        if domain and (t.subject_area or "Ungrouped") != domain:
            continue
        if kind and t.kind != kind:
            continue
        out.append(
            {
                "name": t.qualified_name,
                "domain": t.subject_area,
                "kind": t.kind,
                "rows": t.row_count,
                "columns": t.column_count,
                "pii_columns": sum(1 for c in t.columns if c.is_pii),
            }
        )
    return out


def tool_describe_table(catalog: Catalog, name: str) -> dict:
    """Full detail for one table: columns (with PII), primary key, relationships."""
    t = catalog.table_map().get(name)
    if t is None:
        # tolerate an unqualified name
        matches = [x for x in catalog.tables if x.name.lower() == name.lower()]
        t = matches[0] if matches else None
    if t is None:
        return {"error": f"table '{name}' not found"}
    return {
        "name": t.qualified_name,
        "domain": t.subject_area,
        "kind": t.kind,
        "row_count": t.row_count,
        "primary_key": t.primary_key,
        "description": t.description,
        "columns": [
            {
                "name": c.name,
                "type": c.data_type,
                "nullable": c.is_nullable,
                "primary_key": c.is_primary_key,
                "pii": c.pii_kind if c.is_pii else None,
            }
            for c in t.columns
        ],
        "relationships": [
            {
                "to": fk.ref_qualified,
                "on": f"{fk.parent_column} = {fk.ref_table}.{fk.ref_column}",
                "inferred": fk.inferred,
            }
            for fk in t.foreign_keys
        ],
    }


def tool_find_join_path(catalog: Catalog, from_table: str, to_table: str) -> dict:
    """How two tables connect — the shortest chain of joins."""
    steps = paths.find_path(catalog, from_table, to_table)
    return {
        "from": from_table,
        "to": to_table,
        "connected": steps is not None and steps != [],
        "steps": steps or [],
        "text": paths.path_to_text(steps, from_table, to_table),
    }


def tool_search(catalog: Catalog, query: str) -> list:
    """Find tables whose name or any column name contains the query string."""
    q = query.lower().strip()
    hits = []
    for t in catalog.tables:
        cols = [c.name for c in t.columns if q in c.name.lower()]
        if q in t.qualified_name.lower() or cols:
            hits.append(
                {"table": t.qualified_name, "domain": t.subject_area, "matched_columns": cols}
            )
    return hits


def tool_agent_context(catalog: Catalog) -> dict:
    """The whole compact, agent-ready context for the schema."""
    return agentcontext.to_agent_context(catalog)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="schema-scout-mcp", description=__doc__)
    parser.add_argument("--catalog", default="out/catalog.json", help="path to a generated catalog.json")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            "The MCP server needs the 'mcp' package. Install with: pip install 'schema-scout[mcp]'"
        )

    mcp = FastMCP("schema-scout")

    @mcp.tool()
    def list_domains() -> list:
        """List subject areas (domains) with table, row and PII counts."""
        return tool_list_domains(catalog)

    @mcp.tool()
    def list_tables(domain: str = "", kind: str = "") -> list:
        """List tables, optionally filtered by domain or kind (fact/dimension/bridge/reference)."""
        return tool_list_tables(catalog, domain or None, kind or None)

    @mcp.tool()
    def describe_table(name: str) -> dict:
        """Describe one table: columns, PII flags, primary key, and relationships."""
        return tool_describe_table(catalog, name)

    @mcp.tool()
    def find_join_path(from_table: str, to_table: str) -> dict:
        """Find the shortest chain of joins connecting two tables."""
        return tool_find_join_path(catalog, from_table, to_table)

    @mcp.tool()
    def search(query: str) -> list:
        """Search tables and columns by name."""
        return tool_search(catalog, query)

    @mcp.tool()
    def agent_context() -> dict:
        """Return the full compact, agent-ready context for the whole schema."""
        return tool_agent_context(catalog)

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
