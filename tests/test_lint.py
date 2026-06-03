"""Schema-health (lint) tests — no database required."""
from schema_scout import classify, domains, lint, relationships
from schema_scout._demo import build_demo_catalog
from schema_scout.model import Catalog, Column, Table


def _ready():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    return cat


def _codes(findings):
    return {f["code"] for f in findings}


def test_demo_finds_constant_and_all_null():
    findings = lint.lint_catalog(_ready())
    codes = _codes(findings)
    assert "constant" in codes        # customers.record_status
    assert "all_null" in codes        # orders.legacy_ref


def test_no_primary_key_flagged():
    t = Table(schema="dbo", name="junk", row_count=10)
    t.columns = [Column("dbo", "junk", "x", 1, "int", True)]
    findings = lint.lint_catalog(Catalog(tables=[t]))
    assert any(f["code"] == "no_primary_key" for f in findings)


def test_orphan_table_flagged():
    t = Table(schema="dbo", name="lonely", row_count=10, primary_key=["id"])
    t.columns = [Column("dbo", "lonely", "id", 1, "int", False, is_primary_key=True)]
    findings = lint.lint_catalog(Catalog(tables=[t]))
    assert any(f["code"] == "orphan_table" for f in findings)


def test_findings_carry_domain():
    cat = _ready()
    findings = lint.lint_catalog(cat)
    assert all("domain" in f for f in findings)


def test_severity_sort_and_summary():
    findings = lint.lint_catalog(_ready())
    sev = [f["severity"] for f in findings]
    order = {"high": 0, "medium": 1, "low": 2}
    assert sev == sorted(sev, key=lambda s: order[s])
    summ = lint.summarize_lint(findings)
    assert summ["high"] + summ["medium"] + summ["low"] == len(findings)
