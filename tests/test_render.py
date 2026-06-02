"""Render tests — no database required."""
import json

from schema_scout import classify, relationships, render
from schema_scout._demo import build_demo_catalog


def _full_catalog():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    return cat


def test_json_is_valid_and_complete():
    cat = _full_catalog()
    data = json.loads(render.to_json(cat))
    assert data["table_count"] == 4
    names = {t["qualified_name"] for t in data["tables"]}
    assert "dbo.orders" in names


def test_markdown_has_sections():
    cat = _full_catalog()
    md = render.to_markdown(cat)
    assert "# Data catalog" in md
    assert "## Tables by size" in md
    assert "Potential PII" in md  # demo has an email column
    assert "dbo.orders" in md


def test_mermaid_is_erdiagram_with_edges():
    cat = _full_catalog()
    mmd = render.to_mermaid(cat)
    assert mmd.startswith("erDiagram")
    # the inferred orders->customers edge should appear
    assert "dbo_customers" in mmd
    assert "||--o{" in mmd


def test_mermaid_scoped_to_subset():
    cat = _full_catalog()
    mmd = render.to_mermaid(cat, tables=["dbo.orders", "dbo.customers"])
    assert "dbo_products" not in mmd
    assert "dbo_orders" in mmd
