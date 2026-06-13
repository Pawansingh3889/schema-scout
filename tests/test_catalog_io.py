"""Round-trip tests for loading a rendered catalog back into the model."""
from schema_scout import catalog_io, classify, domains, relationships, render
from schema_scout._demo import build_demo_catalog


def _round_trip():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    data = render.to_dict(cat)
    return catalog_io.catalog_from_dict(data)


def test_tables_and_columns_restored():
    cat = _round_trip()
    assert len(cat.tables) == 4
    orders = cat.get("dbo", "orders")
    assert orders is not None
    assert orders.kind == "fact"
    assert orders.primary_key == ["id"]
    assert orders.column("customer_id") is not None


def test_relationships_restored():
    cat = _round_trip()
    # the inferred orders.customer_id -> customers edge survives the round trip
    edges = {(fk.parent_table, fk.parent_column, fk.ref_table) for fk in cat.relationships}
    assert ("orders", "customer_id", "customers") in edges


def test_pii_restored():
    cat = _round_trip()
    email = cat.get("dbo", "customers").column("email")
    assert email.is_pii and email.pii_kind == "email"
