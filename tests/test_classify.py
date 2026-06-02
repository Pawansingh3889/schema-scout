"""Classification and PII tests — no database required."""
from schema_scout import classify
from schema_scout._demo import build_demo_catalog
from schema_scout.model import Column, Table


def test_pii_by_name():
    c = Column("dbo", "customers", "email", 1, "nvarchar", True)
    is_pii, kind = classify.detect_pii(c)
    assert is_pii and kind == "email"

    c2 = Column("dbo", "staff", "date_of_birth", 1, "date", True)
    is_pii2, kind2 = classify.detect_pii(c2)
    assert is_pii2 and kind2 == "dob"


def test_pii_by_value():
    c = Column("dbo", "x", "contact", 1, "nvarchar", True)
    c.sample_values = ["someone@example.com", "other@example.com"]
    is_pii, kind = classify.detect_pii(c)
    assert is_pii and kind == "email"


def test_non_pii():
    c = Column("dbo", "products", "unit_cost_per_kg", 1, "decimal", True)
    is_pii, _ = classify.detect_pii(c)
    assert not is_pii


def test_bridge_detection():
    cat = build_demo_catalog()
    classify.classify_catalog(cat)
    order_tags = cat.get("dbo", "order_tags")
    assert order_tags.kind == "bridge"


def test_dimension_and_fact():
    cat = build_demo_catalog()
    # make the missing FK visible so orders looks like a real fact table
    from schema_scout import relationships as rel

    rel.merge_inferred(cat, rel.infer_relationships(cat))
    classify.classify_catalog(cat)
    assert cat.get("dbo", "customers").kind in {"dimension", "reference"}
    assert cat.get("dbo", "orders").kind == "fact"


def test_pk_candidates_from_sample():
    t = Table(schema="dbo", name="t", row_count=100)
    uniq = Column("dbo", "t", "code", 1, "nvarchar", False)
    uniq.sampled_rows, uniq.null_count, uniq.distinct_count = 100, 0, 100
    dup = Column("dbo", "t", "status", 2, "nvarchar", True)
    dup.sampled_rows, dup.null_count, dup.distinct_count = 100, 5, 3
    t.columns = [uniq, dup]
    assert classify.pk_candidates(t) == ["code"]


def test_annotate_pii_counts():
    cat = build_demo_catalog()
    flagged = classify.annotate_pii(cat)
    assert flagged >= 1
    assert cat.get("dbo", "customers").column("email").is_pii
