"""Exact-profiling tests.

The query builder and result applier are pure, so the full exact path is
tested without a database by feeding a fake result row.
"""
from schema_scout import profile
from schema_scout.model import Column, Table


def _table():
    t = Table(schema="dbo", name="orders", row_count=85000, primary_key=["id"])
    t.columns = [
        Column("dbo", "orders", "id", 1, "int", False, is_primary_key=True, is_identity=True),
        Column("dbo", "orders", "customer_id", 2, "int", False),
        Column("dbo", "orders", "notes", 3, "nvarchar", True, max_length=-1),  # MAX
        Column("dbo", "orders", "blob", 4, "varbinary", True),
        Column("dbo", "orders", "quantity_kg", 5, "decimal", True),
    ]
    return t


def test_can_aggregate_by_type():
    cols = {c.name: c for c in _table().columns}
    assert profile.can_aggregate(cols["id"]) is True
    assert profile.can_aggregate(cols["quantity_kg"]) is True
    assert profile.can_aggregate(cols["notes"]) is False  # nvarchar(MAX)
    assert profile.can_aggregate(cols["blob"]) is False  # varbinary


def test_key_like_columns():
    keys = profile.key_like_columns(_table())
    assert "id" in keys  # PK + identity + ends with 'id'
    assert "customer_id" in keys
    assert "quantity_kg" not in keys
    assert "notes" not in keys


def test_build_query_skips_non_aggregatable_min_max():
    t = _table()
    sql, plan = profile.build_exact_profile_query(t, columns=["id", "notes"])
    # both get a null count
    kinds = {(col.name, kind) for col, kind, _ in plan}
    assert ("id", "nulls") in kinds
    assert ("notes", "nulls") in kinds
    # but only the aggregatable one gets distinct/min/max
    assert ("id", "distinct") in kinds
    assert ("notes", "distinct") not in kinds
    assert "COUNT_BIG(*)" in sql
    assert "[dbo].[orders]" in sql


def test_empty_when_no_columns_match():
    sql, plan = profile.build_exact_profile_query(_table(), columns=["does_not_exist"])
    assert sql == "" and plan == []


def test_apply_results_sets_exact_mode_and_full_counts():
    t = _table()
    sql, plan = profile.build_exact_profile_query(t, columns=["id", "customer_id"])
    # fake the DB result row keyed by the aliases in the plan
    result = {"__total": 85000}
    for col, kind, alias in plan:
        if kind == "nulls":
            result[alias] = 0 if col.name == "id" else 12
        elif kind == "distinct":
            result[alias] = 85000 if col.name == "id" else 1180
        elif kind == "min":
            result[alias] = 1
        elif kind == "max":
            result[alias] = 999

    profile.apply_exact_results(t, plan, result)

    cid = t.column("id")
    assert cid.profile_mode == "exact"
    assert cid.sampled_rows == 85000  # full table, not a sample
    assert cid.null_count == 0
    assert cid.distinct_count == 85000
    assert cid.null_pct == 0.0

    cust = t.column("customer_id")
    assert cust.null_count == 12
    assert cust.distinct_count == 1180
