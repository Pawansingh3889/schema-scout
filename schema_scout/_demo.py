"""A synthetic catalog so the inference/classify/render pipeline can be run
and demonstrated without any database connection.

Models a tiny food-manufacturing-shaped schema with a deliberately *missing*
foreign key (orders.customer_id is not declared) so the inference step has
something to find.
"""
from __future__ import annotations

from schema_scout.model import Catalog, Column, ForeignKey, Table


def _col(schema, table, name, ordinal, dtype, nullable=True, pk=False, samples=None):
    c = Column(
        schema=schema,
        table=table,
        name=name,
        ordinal=ordinal,
        data_type=dtype,
        is_nullable=nullable,
        is_primary_key=pk,
    )
    if samples is not None:
        c.sample_values = samples
        c.sampled_rows = 100
        c.null_count = 0
        c.distinct_count = len(samples)
    return c


def build_demo_catalog() -> Catalog:
    customers = Table(schema="dbo", name="customers", row_count=1200, primary_key=["id"])
    customers.columns = [
        _col("dbo", "customers", "id", 1, "int", nullable=False, pk=True),
        _col("dbo", "customers", "name", 2, "nvarchar"),
        _col("dbo", "customers", "email", 3, "nvarchar", samples=["a@b.com", "c@d.com"]),
        _col("dbo", "customers", "city", 4, "nvarchar"),
    ]

    products = Table(schema="dbo", name="products", row_count=340, primary_key=["id"])
    products.columns = [
        _col("dbo", "products", "id", 1, "int", nullable=False, pk=True),
        _col("dbo", "products", "description", 2, "nvarchar"),
        _col("dbo", "products", "unit_cost_per_kg", 3, "decimal"),
    ]

    orders = Table(schema="dbo", name="orders", row_count=85000, primary_key=["id"])
    orders.columns = [
        _col("dbo", "orders", "id", 1, "int", nullable=False, pk=True),
        # customer_id deliberately has NO declared FK -> inference must find it
        _col("dbo", "orders", "customer_id", 2, "int", nullable=False),
        _col("dbo", "orders", "product_id", 3, "int", nullable=False),
        _col("dbo", "orders", "quantity_kg", 4, "decimal"),
        _col("dbo", "orders", "order_date", 5, "date"),
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

    order_tags = Table(schema="dbo", name="order_tags", row_count=120000, primary_key=["order_id", "tag_id"])
    order_tags.columns = [
        _col("dbo", "order_tags", "order_id", 1, "int", nullable=False, pk=True),
        _col("dbo", "order_tags", "tag_id", 2, "int", nullable=False, pk=True),
    ]

    cat = Catalog(
        tables=[customers, products, orders, order_tags],
        relationships=list(orders.foreign_keys),
    )
    return cat
