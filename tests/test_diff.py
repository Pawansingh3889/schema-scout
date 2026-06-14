import json

from schema_scout.diff import diff_catalogs, format_diff, has_changes
from schema_scout.model import Catalog, Column, Table


def col(table, name, data_type="int", nullable=False, pk=False):
    return Column(
        schema="dbo",
        table=table,
        name=name,
        ordinal=0,
        data_type=data_type,
        is_nullable=nullable,
        is_primary_key=pk,
    )


def tbl(name, columns, row_count=0, pk=None):
    return Table(
        schema="dbo",
        name=name,
        row_count=row_count,
        columns=columns,
        primary_key=pk or [],
    )


def test_no_changes():
    a = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=10, pk=["id"])])
    b = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=10, pk=["id"])])
    d = diff_catalogs(a, b)
    assert not has_changes(d)
    assert d["summary"]["tables_changed"] == 0
    assert "No changes" in format_diff(d)


def test_table_added_and_removed():
    a = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], pk=["id"])])
    b = Catalog(tables=[tbl("customers", [col("customers", "id", pk=True)], pk=["id"])])
    d = diff_catalogs(a, b)
    assert d["tables"]["added"] == ["dbo.customers"]
    assert d["tables"]["removed"] == ["dbo.orders"]
    assert has_changes(d)


def test_column_added_removed_and_type_changed():
    a = Catalog(tables=[tbl("orders", [
        col("orders", "id", pk=True),
        col("orders", "status", "varchar"),
        col("orders", "old_col", "int"),
    ], pk=["id"])])
    b = Catalog(tables=[tbl("orders", [
        col("orders", "id", pk=True),
        col("orders", "status", "int"),   # type changed
        col("orders", "new_col", "int"),  # added
    ], pk=["id"])])
    d = diff_catalogs(a, b)
    ch = d["tables"]["changed"][0]
    assert ch["table"] == "dbo.orders"
    assert ch["columns_added"] == ["new_col"]
    assert ch["columns_removed"] == ["old_col"]
    assert ch["columns_changed"][0]["column"] == "status"
    assert "data_type" in ch["columns_changed"][0]["changed"]
    assert d["summary"]["columns_added"] == 1
    assert d["summary"]["columns_removed"] == 1
    assert d["summary"]["columns_changed"] == 1


def test_row_count_significant_flag():
    a = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=100, pk=["id"])])
    b = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=250, pk=["id"])])
    rc = diff_catalogs(a, b)["tables"]["changed"][0]["row_count"]
    assert (rc["from"], rc["to"], rc["delta"], rc["pct"]) == (100, 250, 150, 150.0)
    assert rc["significant"] is True


def test_row_count_from_zero_has_null_pct():
    a = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=0, pk=["id"])])
    b = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], row_count=5, pk=["id"])])
    rc = diff_catalogs(a, b)["tables"]["changed"][0]["row_count"]
    assert rc["pct"] is None
    assert rc["significant"] is True


def test_readiness_delta_and_json_serialisable():
    a = Catalog(tables=[tbl("orders", [col("orders", "id", pk=True)], pk=["id"])])
    b = Catalog(tables=[tbl("orders", [col("orders", "id", pk=False)], pk=[])])  # PK dropped
    d = diff_catalogs(a, b)
    assert d["readiness"]["delta"] <= 0
    json.dumps(d)  # must not raise (no sets, no inf)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
