"""AI-readiness score tests — no database required."""
from schema_scout import classify, domains, readiness, relationships
from schema_scout._demo import build_demo_catalog


def _ready(describe=False):
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    if describe:
        for t in cat.tables:
            t.description = "demo description"
    return cat


def test_score_in_range_and_shape():
    r = readiness.compute_readiness(_ready())
    assert 0 <= r["score"] <= 100
    assert r["grade"] in {"A", "B", "C", "D", "F"}
    assert set(r["components"]) == {"keys", "relationships", "documentation", "cleanliness"}


def test_documentation_component_reflects_descriptions():
    no_doc = readiness.compute_readiness(_ready(describe=False))
    with_doc = readiness.compute_readiness(_ready(describe=True))
    assert no_doc["components"]["documentation"] == 0.0
    assert with_doc["components"]["documentation"] == 100.0
    assert with_doc["score"] > no_doc["score"]


def test_recommendations_flag_missing_descriptions():
    r = readiness.compute_readiness(_ready(describe=False))
    assert any("description" in rec for rec in r["recommendations"])


def test_all_pk_demo_keys_component_full():
    # every table in the small demo has a primary key
    r = readiness.compute_readiness(_ready())
    assert r["components"]["keys"] == 100.0
