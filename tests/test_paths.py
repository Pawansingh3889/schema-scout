"""Join-path tests — no database required."""
from schema_scout import paths, relationships
from schema_scout._demo import build_demo_catalog


def _connected_demo():
    cat = build_demo_catalog()
    # merge the inferred orders.customer_id -> customers edge
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    return cat


def test_direct_path():
    cat = _connected_demo()
    steps = paths.find_path(cat, "dbo.orders", "dbo.customers")
    assert steps is not None and len(steps) == 1
    assert steps[0]["from"] == "dbo.orders" and steps[0]["to"] == "dbo.customers"


def test_two_hop_path():
    cat = _connected_demo()
    steps = paths.find_path(cat, "dbo.customers", "dbo.products")
    # customers -> orders -> products
    assert steps is not None and len(steps) == 2
    chain = [steps[0]["from"], steps[0]["to"], steps[1]["to"]]
    assert chain[0] == "dbo.customers" and chain[-1] == "dbo.products"


def test_same_table():
    cat = _connected_demo()
    assert paths.find_path(cat, "dbo.orders", "dbo.orders") == []


def test_disconnected_returns_none():
    cat = _connected_demo()
    # order_tags has no relationships in the demo -> unreachable
    assert paths.find_path(cat, "dbo.orders", "dbo.order_tags") is None


def test_unknown_table_returns_none():
    cat = _connected_demo()
    assert paths.find_path(cat, "dbo.orders", "dbo.nope") is None


def test_path_to_text():
    cat = _connected_demo()
    txt = paths.path_to_text(paths.find_path(cat, "dbo.customers", "dbo.products"))
    assert "join" in txt.lower()
    assert paths.path_to_text(None, "a", "b").startswith("No join path")
