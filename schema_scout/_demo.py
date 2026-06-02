"""A synthetic catalog so the inference/classify/render pipeline can be run
and demonstrated without any database connection.

Models a tiny food-manufacturing-shaped schema with a deliberately *missing*
foreign key (orders.customer_id is not declared) so the inference step has
something to find. Columns carry realistic (fabricated) profile stats so the
``demo`` command shows the same kind of output a real profiled run produces.
"""
from __future__ import annotations

from schema_scout.model import Catalog, Column, ForeignKey, Table


def _col(
    schema,
    table,
    name,
    ordinal,
    dtype,
    nullable=True,
    pk=False,
    identity=False,
    mode=None,
    rows=None,
    nulls=None,
    distinct=None,
    vmin=None,
    vmax=None,
    samples=None,
):
    c = Column(
        schema=schema,
        table=table,
        name=name,
        ordinal=ordinal,
        data_type=dtype,
        is_nullable=nullable,
        is_primary_key=pk,
        is_identity=identity,
    )
    c.profile_mode = mode
    c.sampled_rows = rows
    c.null_count = nulls
    c.distinct_count = distinct
    c.min_value = vmin
    c.max_value = vmax
    c.sample_values = samples or []
    return c


def build_demo_catalog() -> Catalog:
    customers = Table(schema="dbo", name="customers", row_count=1200, primary_key=["id"])
    customers.columns = [
        _col("dbo", "customers", "id", 1, "int", nullable=False, pk=True, identity=True,
             mode="exact", rows=1200, nulls=0, distinct=1200, vmin="1", vmax="1200"),
        _col("dbo", "customers", "name", 2, "nvarchar",
             mode="sampled", rows=1200, nulls=0, distinct=1187,
             samples=["Greggs", "Co-op Food", "Morrisons", "Booths"]),
        _col("dbo", "customers", "email", 3, "nvarchar",
             mode="sampled", rows=1200, nulls=132, distinct=1051,
             samples=["orders@greggs.co.uk", "buying@coop.co.uk"]),
        _col("dbo", "customers", "city", 4, "nvarchar",
             mode="sampled", rows=1200, nulls=18, distinct=214,
             samples=["Leeds", "Hull", "Manchester", "Newcastle"]),
    ]

    products = Table(schema="dbo", name="products", row_count=340, primary_key=["id"])
    products.columns = [
        _col("dbo", "products", "id", 1, "int", nullable=False, pk=True, identity=True,
             mode="exact", rows=340, nulls=0, distinct=340, vmin="1", vmax="340"),
        _col("dbo", "products", "description", 2, "nvarchar",
             mode="sampled", rows=340, nulls=0, distinct=338,
             samples=["Pork Sausage 400g", "Beef Burger 2pk", "Chicken Fillet 1kg"]),
        _col("dbo", "products", "unit_cost_per_kg", 3, "decimal",
             mode="sampled", rows=340, nulls=0, distinct=176, vmin="1.20", vmax="14.50",
             samples=["3.40", "5.10", "2.85"]),
    ]

    orders = Table(schema="dbo", name="orders", row_count=85000, primary_key=["id"])
    orders.columns = [
        _col("dbo", "orders", "id", 1, "int", nullable=False, pk=True, identity=True,
             mode="exact", rows=85000, nulls=0, distinct=85000, vmin="1", vmax="85000"),
        # customer_id deliberately has NO declared FK -> inference must find it
        _col("dbo", "orders", "customer_id", 2, "int", nullable=False,
             mode="exact", rows=85000, nulls=0, distinct=1200, vmin="1", vmax="1200"),
        _col("dbo", "orders", "product_id", 3, "int", nullable=False,
             mode="exact", rows=85000, nulls=0, distinct=340, vmin="1", vmax="340"),
        _col("dbo", "orders", "quantity_kg", 4, "decimal",
             mode="sampled", rows=50000, nulls=0, distinct=4180, vmin="0.50", vmax="980.00",
             samples=["12.00", "25.00", "4.50"]),
        _col("dbo", "orders", "order_date", 5, "date",
             mode="sampled", rows=50000, nulls=0, distinct=731,
             vmin="2024-06-01", vmax="2026-05-31"),
    ]
    # one declared FK so the demo shows declared + inferred side by side
    orders.foreign_keys = [
        ForeignKey(
            name="FK_orders_products",
            parent_schema="dbo",
            parent_table="orders",
            parent_column="product_id",
            ref_schema="dbo",
            ref_table="products",
            ref_column="id",
        )
    ]

    order_tags = Table(
        schema="dbo", name="order_tags", row_count=120000, primary_key=["order_id", "tag_id"]
    )
    order_tags.columns = [
        _col("dbo", "order_tags", "order_id", 1, "int", nullable=False, pk=True,
             mode="exact", rows=120000, nulls=0, distinct=85000, vmin="1", vmax="85000"),
        _col("dbo", "order_tags", "tag_id", 2, "int", nullable=False, pk=True,
             mode="exact", rows=120000, nulls=0, distinct=12, vmin="1", vmax="12"),
    ]

    cat = Catalog(
        tables=[customers, products, orders, order_tags],
        relationships=list(orders.foreign_keys),
    )
    return cat
