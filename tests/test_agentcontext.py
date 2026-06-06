"""Agent-context export tests — no database required."""
import json

from schema_scout import agentcontext, classify, domains, relationships
from schema_scout._demo import build_demo_catalog


def _ready():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    classify.annotate_pii(cat)
    classify.classify_catalog(cat)
    domains.infer_domains(cat)
    return cat


def test_structure_and_summary():
    ctx = agentcontext.to_agent_context(_ready())
    assert ctx["format"] == "schema-scout/agent-context/1"
    assert ctx["summary"]["tables"] == 4
    assert ctx["summary"]["pii_columns"] >= 1
    names = {t["name"] for t in ctx["tables"]}
    assert "dbo.orders" in names


def test_joins_include_inferred_with_keys():
    ctx = agentcontext.to_agent_context(_ready())
    orders = next(t for t in ctx["tables"] if t["name"] == "dbo.orders")
    targets = {j["to"]: j for j in orders["joins"]}
    assert "dbo.customers" in targets  # the inferred FK
    j = targets["dbo.customers"]
    assert j["inferred"] is True
    assert "orders.customer_id = customers.id" in j["on"]


def test_columns_flag_pk_fk_pii():
    ctx = agentcontext.to_agent_context(_ready())
    orders = next(t for t in ctx["tables"] if t["name"] == "dbo.orders")
    cols = {c["name"]: c for c in orders["columns"]}
    assert cols["id"].get("pk") is True
    assert cols["customer_id"].get("fk") == "dbo.customers.id"

    customers = next(t for t in ctx["tables"] if t["name"] == "dbo.customers")
    ccols = {c["name"]: c for c in customers["columns"]}
    assert ccols["email"].get("pii") == "email"


def test_compact_only_present_keys():
    # a plain non-key, non-pii column shouldn't carry empty pk/fk/pii keys
    ctx = agentcontext.to_agent_context(_ready())
    customers = next(t for t in ctx["tables"] if t["name"] == "dbo.customers")
    name_col = next(c for c in customers["columns"] if c["name"] == "name")
    assert "pk" not in name_col and "fk" not in name_col and "pii" not in name_col


def test_json_is_valid():
    data = json.loads(agentcontext.to_agent_json(_ready()))
    assert data["tables"]
