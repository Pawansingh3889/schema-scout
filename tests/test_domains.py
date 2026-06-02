"""Domain inference tests — no database required."""
from schema_scout import domains
from schema_scout._demo import build_demo_catalog
from schema_scout.model import Catalog, Column, Table


def test_first_token():
    assert domains.first_token("SalesOrder") == "sales"
    assert domains.first_token("sal_order_line") == "sal"
    assert domains.first_token("orders") == "orders"
    assert domains.first_token("ProductionRun") == "production"


def _prefixed_catalog():
    names = ["SalesOrder", "SalesOrderLine", "SalesInvoice",
             "ProductionRun", "ProductionBatch"]
    tables = []
    for i, n in enumerate(names):
        t = Table(schema="dbo", name=n, row_count=100 * (i + 1), primary_key=["id"])
        t.columns = [Column("dbo", n, "id", 1, "int", False, is_primary_key=True)]
        tables.append(t)
    return Catalog(tables=tables)


def test_prefix_strategy_groups_modules():
    cat = _prefixed_catalog()
    assign = domains.infer_domains(cat, strategy="prefix")
    assert assign["dbo.SalesOrder"] == "Sales"
    assert assign["dbo.SalesInvoice"] == "Sales"
    assert assign["dbo.ProductionRun"] == "Production"
    assert len(set(assign.values())) == 2


def test_auto_picks_prefix_when_meaningful():
    cat = _prefixed_catalog()
    domains.infer_domains(cat, strategy="auto")
    # five tables, two shared prefixes -> prefix grouping wins
    assert {t.subject_area for t in cat.tables} == {"Sales", "Production"}


def test_components_strategy_on_demo():
    cat = build_demo_catalog()
    # need the inferred FK so orders<->customers are connected
    from schema_scout import relationships as rel

    rel.merge_inferred(cat, rel.infer_relationships(cat))
    assign = domains.infer_domains(cat, strategy="components")
    # orders, customers, products are all connected -> one domain
    assert assign["dbo.orders"] == assign["dbo.customers"] == assign["dbo.products"]
    # order_tags is isolated -> its own domain
    assert assign["dbo.order_tags"] != assign["dbo.orders"]


def test_summarize_rolls_up_metrics():
    cat = build_demo_catalog()
    from schema_scout import classify, relationships as rel

    rel.merge_inferred(cat, rel.infer_relationships(cat))
    classify.annotate_pii(cat)
    domains.infer_domains(cat, strategy="components")
    summary = domains.summarize_domains(cat)
    total_tables = sum(d["tables"] for d in summary)
    total_pii = sum(d["pii"] for d in summary)
    assert total_tables == 4
    assert total_pii >= 1  # customers.email
    # sorted by rows descending
    assert summary == sorted(summary, key=lambda d: d["rows"], reverse=True)
