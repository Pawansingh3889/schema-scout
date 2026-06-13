"""MCP tool-logic tests (no `mcp` package or live protocol needed)."""
from schema_scout import (
    catalog_io,
    classify,
    domains,
    mcp_server,
    relationships,
    render,
)
from schema_scout._demo import build_demo_catalog


def _catalog():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    # round-trip through the rendered form, the way the server loads it
    return catalog_io.catalog_from_dict(render.to_dict(cat))


def test_list_tables_and_filter():
    cat = _catalog()
    allt = mcp_server.tool_list_tables(cat)
    assert {t["name"] for t in allt} >= {"dbo.orders", "dbo.customers"}
    facts = mcp_server.tool_list_tables(cat, kind="fact")
    assert all(t["kind"] == "fact" for t in facts)
    assert any(t["name"] == "dbo.orders" for t in facts)


def test_describe_table():
    cat = _catalog()
    d = mcp_server.tool_describe_table(cat, "dbo.orders")
    assert d["name"] == "dbo.orders"
    cols = {c["name"]: c for c in d["columns"]}
    assert cols["id"]["primary_key"] is True
    assert any(r["to"] == "dbo.customers" for r in d["relationships"])
    # unqualified name also resolves
    assert mcp_server.tool_describe_table(cat, "customers")["name"] == "dbo.customers"
    assert "error" in mcp_server.tool_describe_table(cat, "nope")


def test_find_join_path():
    cat = _catalog()
    r = mcp_server.tool_find_join_path(cat, "dbo.customers", "dbo.products")
    assert r["connected"] is True
    assert len(r["steps"]) == 2
    r2 = mcp_server.tool_find_join_path(cat, "dbo.orders", "dbo.order_tags")
    assert r2["connected"] is False


def test_search_and_domains_and_context():
    cat = _catalog()
    hits = mcp_server.tool_search(cat, "customer")
    assert any(h["table"] == "dbo.customers" or h["matched_columns"] for h in hits)
    doms = mcp_server.tool_list_domains(cat)
    assert sum(d["tables"] for d in doms) == 4
    ctx = mcp_server.tool_agent_context(cat)
    assert ctx["format"].startswith("schema-scout/agent-context")
