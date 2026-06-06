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
        # constant column -> a health finding
        _col("dbo", "customers", "record_status", 5, "nvarchar",
             mode="sampled", rows=1200, nulls=0, distinct=1, samples=["active"]),
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
        # legacy column nobody populates -> an all-null health finding
        _col("dbo", "orders", "legacy_ref", 6, "nvarchar",
             mode="sampled", rows=50000, nulls=50000, distinct=0),
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


def build_large_demo_catalog() -> Catalog:
    """A bigger synthetic schema (~30 tables, several domains) for showcasing
    the dashboard at a realistic scale. Not used by the tests.

    Food-manufacturing flavoured, with declared and undeclared foreign keys, a
    cross-domain link or two, PII spread across people/customer/supplier
    tables, and a couple of deliberate health problems (a no-PK orphan log, an
    all-null column, a constant column).
    """
    tables: list = []
    declared: list = []
    I, S, D, DT, TS, BIT, TM = "int", "nvarchar", "decimal", "date", "datetime", "bit", "time"

    def t(name, rows, cols, fks=(), pk=("id",)):
        columns = [
            _col("dbo", name, cn, i, dt, nullable=(cn not in pk), pk=(cn in pk))
            for i, (cn, dt) in enumerate(cols, start=1)
        ]
        tb = Table(schema="dbo", name=name, row_count=rows, primary_key=list(pk))
        tb.columns = columns
        for col, rt, rc in fks:
            fk = ForeignKey(
                name=f"FK_{name}_{col}", parent_schema="dbo", parent_table=name,
                parent_column=col, ref_schema="dbo", ref_table=rt, ref_column=rc,
            )
            tb.foreign_keys.append(fk)
            declared.append(fk)
        tables.append(tb)
        return tb

    # shared reference tables (unprefixed) -> referenced *undeclared* so the
    # inference step has cross-table links to recover
    t("regions", 14, [("id", I), ("name", S)])
    t("currencies", 8, [("id", I), ("code", S)])

    # --- Sales ---
    t("sales_customers", 12000, [("id", I), ("name", S), ("email", S), ("phone", S),
                                 ("city", S), ("region_id", I), ("account_status", S)])
    t("sales_orders", 5200000, [("id", I), ("customer_id", I), ("currency_id", I),
                                ("order_date", DT), ("status", S), ("total_value", D)],
      fks=[("customer_id", "sales_customers", "id")])
    t("sales_order_lines", 41000000, [("id", I), ("order_id", I), ("product_id", I),
                                      ("qty_kg", D), ("line_value", D)],
      fks=[("order_id", "sales_orders", "id"), ("product_id", "inventory_products", "id")])
    t("sales_invoices", 5000000, [("id", I), ("order_id", I), ("invoice_date", DT), ("amount", D)],
      fks=[("order_id", "sales_orders", "id")])
    t("sales_shipments", 4800000, [("id", I), ("order_id", I), ("shipped_date", DT), ("carrier", S)],
      fks=[("order_id", "sales_orders", "id")])
    t("sales_returns", 240000, [("id", I), ("order_id", I), ("reason", S), ("qty_kg", D)],
      fks=[("order_id", "sales_orders", "id")])
    t("sales_audit_log", 95000000, [("event_time", TS), ("payload", S)], pk=())  # no PK -> health

    # --- Production ---
    t("production_lines", 40, [("id", I), ("name", S), ("area", S)])
    t("production_recipes", 1200, [("id", I), ("product_id", I), ("version", S)],
      fks=[("product_id", "inventory_products", "id")])
    t("production_runs", 900000, [("id", I), ("line_id", I), ("recipe_id", I),
                                  ("run_date", DT), ("yield_pct", D)],
      fks=[("line_id", "production_lines", "id"), ("recipe_id", "production_recipes", "id")])
    t("production_outputs", 8000000, [("id", I), ("run_id", I), ("product_id", I), ("quantity_kg", D)],
      fks=[("run_id", "production_runs", "id"), ("product_id", "inventory_products", "id")])
    t("production_downtime", 120000, [("id", I), ("line_id", I), ("minutes", I), ("reason", S)],
      fks=[("line_id", "production_lines", "id")])

    # --- Inventory ---
    t("inventory_products", 3400, [("id", I), ("description", S), ("unit_cost_per_kg", D), ("is_active", BIT)])
    t("inventory_warehouses", 12, [("id", I), ("name", S), ("location", S)])
    t("inventory_stock", 180000, [("id", I), ("product_id", I), ("warehouse_id", I), ("qty_kg", D)],
      fks=[("product_id", "inventory_products", "id"), ("warehouse_id", "inventory_warehouses", "id")])
    t("inventory_movements", 60000000, [("id", I), ("product_id", I), ("run_id", I),
                                        ("moved_at", TS), ("qty_kg", D)],
      fks=[("product_id", "inventory_products", "id"), ("run_id", "production_runs", "id")])
    t("inventory_batches", 2000000, [("id", I), ("product_id", I), ("batch_code", S), ("expiry_date", DT)],
      fks=[("product_id", "inventory_products", "id")])

    # --- Procurement ---
    t("procurement_suppliers", 2100, [("id", I), ("name", S), ("contact_email", S),
                                      ("contact_phone", S), ("country", S)])
    t("procurement_purchase_orders", 600000, [("id", I), ("supplier_id", I), ("order_date", DT), ("total", D)],
      fks=[("supplier_id", "procurement_suppliers", "id")])
    t("procurement_po_lines", 3000000, [("id", I), ("purchase_order_id", I), ("product_id", I), ("qty_kg", D)],
      fks=[("purchase_order_id", "procurement_purchase_orders", "id"),
           ("product_id", "inventory_products", "id")])
    t("procurement_receipts", 580000, [("id", I), ("purchase_order_id", I), ("received_date", DT)],
      fks=[("purchase_order_id", "procurement_purchase_orders", "id")])

    # --- People ---
    t("people_departments", 45, [("id", I), ("name", S)])
    t("people_employees", 3200, [("id", I), ("first_name", S), ("last_name", S), ("email", S),
                                 ("national_insurance_no", S), ("date_of_birth", DT),
                                 ("middle_name", S), ("department_id", I)],
      fks=[("department_id", "people_departments", "id")])
    t("people_shifts", 26000, [("id", I), ("name", S), ("start_time", TM)])
    t("people_assignments", 1100000, [("id", I), ("employee_id", I), ("shift_id", I), ("work_date", DT)],
      fks=[("employee_id", "people_employees", "id"), ("shift_id", "people_shifts", "id")])

    # --- Quality ---
    t("quality_inspections", 1400000, [("id", I), ("run_id", I), ("inspector", S), ("inspected_at", TS)],
      fks=[("run_id", "production_runs", "id")])
    t("quality_nonconformances", 88000, [("id", I), ("inspection_id", I), ("severity", S), ("description", S)],
      fks=[("inspection_id", "quality_inspections", "id")])
    t("quality_capa", 12000, [("id", I), ("nonconformance_id", I), ("status", S)],
      fks=[("nonconformance_id", "quality_nonconformances", "id")])
    t("quality_results", 9000000, [("id", I), ("inspection_id", I), ("metric", S), ("value", D)],
      fks=[("inspection_id", "quality_inspections", "id")])

    by_name = {tb.name: tb for tb in tables}
    # health: an all-null column and a constant column (needs profile stats)
    mn = by_name["people_employees"].column("middle_name")
    mn.profile_mode, mn.sampled_rows, mn.null_count, mn.distinct_count = "sampled", 50000, 50000, 0
    ia = by_name["inventory_products"].column("is_active")
    ia.profile_mode, ia.sampled_rows, ia.null_count, ia.distinct_count = "sampled", 3400, 0, 1
    ia.sample_values = ["1"]

    return Catalog(tables=tables, relationships=list(declared))
