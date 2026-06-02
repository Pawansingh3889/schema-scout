"""Inference tests — no database required."""
from schema_scout import relationships as rel
from schema_scout._demo import build_demo_catalog
from schema_scout.model import Catalog, Column, Table


def test_singularize():
    assert rel.singularize("customers") == "customer"
    assert rel.singularize("categories") == "category"
    assert rel.singularize("addresses") == "address"
    assert rel.singularize("status") == "status"  # -ss not stripped


def test_infers_missing_fk_in_demo():
    cat = build_demo_catalog()
    candidates = rel.infer_relationships(cat)
    edges = {(c.parent_table, c.parent_column, c.ref_table) for c in candidates}
    # orders.customer_id -> customers (undeclared in the demo) must be found
    assert ("orders", "customer_id", "customers") in edges


def test_does_not_reinfer_declared_fk():
    cat = build_demo_catalog()
    candidates = rel.infer_relationships(cat)
    # orders.product_id already has a declared FK -> must NOT be re-inferred
    edges = {(c.parent_table, c.parent_column) for c in candidates}
    assert ("orders", "product_id") not in edges


def test_type_mismatch_lowers_confidence():
    parent = Table(schema="dbo", name="orders", primary_key=["id"])
    parent.columns = [
        Column("dbo", "orders", "id", 1, "int", False, is_primary_key=True),
        Column("dbo", "orders", "customer_id", 2, "nvarchar", True),  # wrong type
    ]
    target = Table(schema="dbo", name="customers", primary_key=["id"])
    target.columns = [Column("dbo", "customers", "id", 1, "int", False, is_primary_key=True)]
    cat = Catalog(tables=[parent, target])
    cands = rel.infer_relationships(cat)
    assert len(cands) == 1
    assert cands[0].confidence < 0.8  # type mismatch penalised


def test_bare_id_references_nothing():
    t = Table(schema="dbo", name="thing", primary_key=["id"])
    t.columns = [Column("dbo", "thing", "id", 1, "int", False, is_primary_key=True)]
    cat = Catalog(tables=[t])
    assert rel.infer_relationships(cat) == []


def test_merge_respects_min_confidence():
    cat = build_demo_catalog()
    cands = rel.infer_relationships(cat)
    before = len(cat.relationships)
    added = rel.merge_inferred(cat, cands, min_confidence=0.99)  # too strict
    assert added == 0
    assert len(cat.relationships) == before
