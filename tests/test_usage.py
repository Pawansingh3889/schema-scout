"""Usage-scoring tests — the matching logic is pure (no database)."""
from schema_scout import usage
from schema_scout._demo import build_demo_catalog


def test_score_usage_ranks_by_executions():
    cat = build_demo_catalog()
    activity = [
        ("SELECT * FROM dbo.orders WHERE id = 1", 1000),
        ("SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id", 500),
        ("SELECT * FROM products", 10),
    ]
    scores = usage.score_usage(cat, activity)
    # orders referenced by two queries totalling 1500 executions
    assert scores["dbo.orders"] == 1500
    assert scores["dbo.customers"] == 500
    assert scores["dbo.products"] == 10
    assert cat.get("dbo", "orders").query_count == 2
    assert cat.get("dbo", "orders").usage_score == 1500.0


def test_word_boundary_avoids_false_match():
    cat = build_demo_catalog()
    # "ordersummary" should NOT count as a hit on table "orders"
    scores = usage.score_usage(cat, [("SELECT * FROM ordersummary", 999)])
    assert scores["dbo.orders"] == 0


def test_bracketed_names_match():
    cat = build_demo_catalog()
    scores = usage.score_usage(cat, [("SELECT * FROM [dbo].[customers]", 7)])
    assert scores["dbo.customers"] == 7


def test_unused_tables_zero():
    cat = build_demo_catalog()
    usage.score_usage(cat, [("SELECT 1", 5)])
    assert all(t.usage_score == 0 for t in cat.tables)
