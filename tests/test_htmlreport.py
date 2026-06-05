"""HTML dashboard tests — no database required."""
from schema_scout import classify, domains, htmlreport, relationships
from schema_scout._demo import build_demo_catalog


def _ready_catalog():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    return cat


def test_html_is_self_contained():
    html = htmlreport.render_html(_ready_catalog())
    assert html.startswith("<!DOCTYPE html>")
    # no external resources -> works offline, nothing leaves the machine
    assert "src=\"http" not in html
    assert "href=\"http" not in html
    assert "cdn" not in html.lower()


def test_html_embeds_data_and_domains():
    html = htmlreport.render_html(_ready_catalog())
    assert "const DATA =" in html
    assert "const DOMAINS =" in html
    assert "const FINDINGS =" in html
    assert "dbo.orders" in html
    # the inferred FK should be present in the embedded data
    assert "inferred_orders_customer_id" in html


def test_html_token_substitution_complete():
    html = htmlreport.render_html(_ready_catalog())
    assert "__DATA__" not in html
    assert "__DOMAINS__" not in html
    assert "__FINDINGS__" not in html
