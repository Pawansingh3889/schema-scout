"""FK export tests — no database required."""
from schema_scout import exports, relationships
from schema_scout._demo import build_demo_catalog


def _cat():
    cat = build_demo_catalog()
    relationships.merge_inferred(cat, relationships.infer_relationships(cat))
    return cat


def test_sql_constraints_for_inferred():
    sql = exports.to_sql_constraints(_cat(), only_inferred=True)
    assert "ALTER TABLE [dbo].[orders] WITH NOCHECK" in sql
    assert "FOREIGN KEY ([customer_id])" in sql
    assert "REFERENCES [dbo].[customers] ([id])" in sql
    # declared product FK should be excluded when only_inferred=True
    assert "([product_id])" not in sql


def test_sql_constraints_all():
    sql = exports.to_sql_constraints(_cat(), only_inferred=False)
    assert "([product_id])" in sql
    assert "([customer_id])" in sql


def test_dbt_relationships_yaml():
    y = exports.to_dbt_relationships(_cat())
    assert "version: 2" in y
    assert "- relationships:" in y
    assert "source('schema_scout', 'customers')" in y
    assert "field: id" in y
