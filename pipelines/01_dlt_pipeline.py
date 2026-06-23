# Databricks notebook source
# 01_dlt_pipeline.py — Lakeflow Declarative Pipeline (DLT)
# Deploy: Workflows → Delta Live Tables → Create Pipeline
# Target catalog: retail_demo | Compute: Serverless
#
# Tables produced:
#   bronze.customers_raw        — passthrough from raw
#   bronze.orders_raw           — passthrough from raw
#   bronze.inventory_raw        — passthrough from raw
#   bronze.crm_events_raw       — passthrough from raw
#   silver.customers            — cleaned + typed
#   silver.orders               — cleaned + enriched
#   silver.inventory            — deduped + rolling demand
#   silver.crm_summary          — per-customer event counts
#   gold.customer_360           — CORE ENTITY: unified customer profile + churn features
#   gold.inventory_health       — SKU-level reorder status
#   gold.store_staffing_summary — labor gaps by store

import dlt
from pyspark.sql import functions as F

CATALOG = "retail_demo"

# ════════════════════════════════════════════════════════════════════════════════
# BRONZE — raw passthrough tables (already written by data gen notebook)
# DLT wraps them for lineage tracking
# ════════════════════════════════════════════════════════════════════════════════

@dlt.table(name="customers_raw", comment="Raw customer records from Postgres (mocked).")
def bronze_customers():
    return spark.table(f"{CATALOG}.bronze.customers_raw")

@dlt.table(name="orders_raw", comment="Raw order transactions from Postgres (mocked).")
def bronze_orders():
    return spark.table(f"{CATALOG}.bronze.orders_raw")

@dlt.table(name="inventory_raw", comment="Raw daily inventory from MySQL (mocked).")
def bronze_inventory():
    return spark.table(f"{CATALOG}.bronze.inventory_raw")

@dlt.table(name="crm_events_raw", comment="Raw CRM events from Salesforce export (mocked).")
def bronze_crm():
    return spark.table(f"{CATALOG}.bronze.crm_events_raw")

@dlt.table(name="staffing_raw", comment="Raw staffing data from HR system (mocked).")
def bronze_staffing():
    return spark.table(f"{CATALOG}.bronze.staffing_raw")


# ════════════════════════════════════════════════════════════════════════════════
# SILVER — cleaned, typed, deduped
# ════════════════════════════════════════════════════════════════════════════════

@dlt.table(name="customers", comment="Cleaned customer records with store and segment info.")
@dlt.expect("valid_customer_id", "customer_id IS NOT NULL")
@dlt.expect("valid_store_id",    "store_id IS NOT NULL")
def silver_customers():
    return (
        dlt.read("customers_raw")
        .withColumn("age", F.col("age").cast("int"))
        .withColumn("days_since_join", F.col("days_since_join").cast("int"))
        .dropDuplicates(["customer_id"])
    )


@dlt.table(name="orders", comment="Cleaned orders with date parsing and return flag.")
@dlt.expect("valid_order_value", "order_value > 0")
@dlt.expect("valid_order_date",  "order_date IS NOT NULL")
def silver_orders():
    return (
        dlt.read("orders_raw")
        .withColumn("order_date",  F.to_date("order_date"))
        .withColumn("order_value", F.col("order_value").cast("double"))
        .withColumn("is_returned", F.col("is_returned").cast("boolean"))
        .dropDuplicates(["order_id"])
    )


@dlt.table(name="inventory", comment="Deduped inventory with 7-day rolling demand per store+SKU.")
@dlt.expect("valid_qty",       "qty_sold >= 0")
@dlt.expect("valid_inventory", "inventory_on_hand >= 0")
def silver_inventory():
    return spark.sql("""
        WITH deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY store_id, sku_id, txn_date
                    ORDER BY txn_date
                ) AS rn
            FROM LIVE.inventory_raw
        )
        SELECT
            store_id,
            sku_id,
            txn_date,
            qty_sold,
            unit_price,
            inventory_on_hand,
            AVG(qty_sold) OVER (
                PARTITION BY store_id, sku_id
                ORDER BY txn_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS avg_daily_demand_7d,
            CURRENT_TIMESTAMP() AS load_ts
        FROM deduped
        WHERE rn = 1
    """)


@dlt.table(name="crm_summary", comment="Per-customer CRM event counts and last contact date.")
def silver_crm_summary():
    return spark.sql("""
        SELECT
            customer_id,
            COUNT(*) AS total_events,
            SUM(CASE WHEN event_type = 'complaint'       THEN 1 ELSE 0 END) AS complaints,
            SUM(CASE WHEN event_type = 'return_request'  THEN 1 ELSE 0 END) AS return_requests,
            MAX(TO_DATE(event_date)) AS last_contact_date,
            DATEDIFF(CURRENT_DATE(), MAX(TO_DATE(event_date))) AS days_since_last_contact
        FROM LIVE.crm_events_raw
        GROUP BY customer_id
    """)


# ════════════════════════════════════════════════════════════════════════════════
# GOLD — business-ready serving layer
# ════════════════════════════════════════════════════════════════════════════════

@dlt.table(
    name="customer_360",
    comment="CORE ENTITY: unified customer profile with churn features. Source of truth for ML and dashboards."
)
def gold_customer_360():
    return spark.sql("""
        WITH order_features AS (
            SELECT
                customer_id,
                COUNT(*) AS order_count_90d,
                SUM(order_value) AS total_spend_90d,
                ROUND(AVG(order_value), 2) AS avg_order_value,
                MAX(order_date) AS last_order_date,
                DATEDIFF(CURRENT_DATE(), MAX(order_date)) AS recency_days,
                ROUND(SUM(CASE WHEN is_returned THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) AS return_rate
            FROM LIVE.orders
            WHERE order_date >= DATE_SUB(CURRENT_DATE(), 90)
            GROUP BY customer_id
        )
        SELECT
            c.customer_id,
            c.customer_name,
            c.store_id,
            s.region,
            s.state,
            c.segment,
            c.preferred_channel,
            c.age,
            COALESCE(o.order_count_90d,   0)    AS order_count_90d,
            COALESCE(o.total_spend_90d,   0)    AS total_spend_90d,
            COALESCE(o.avg_order_value,   0)    AS avg_order_value,
            o.last_order_date,
            COALESCE(o.recency_days,      999)  AS recency_days,
            COALESCE(o.return_rate,       0)    AS return_rate,
            COALESCE(crm.total_events,    0)    AS crm_events,
            COALESCE(crm.complaints,      0)    AS complaints,
            COALESCE(crm.return_requests, 0)    AS crm_return_requests,
            COALESCE(crm.days_since_last_contact, 999) AS days_since_last_contact,
            CASE WHEN COALESCE(o.recency_days, 999) > 30 THEN 1 ELSE 0 END AS is_churned,
            CURRENT_TIMESTAMP() AS updated_at
        FROM LIVE.customers c
        LEFT JOIN retail_demo.silver.stores s   ON c.store_id = s.store_id
        LEFT JOIN order_features            o   ON c.customer_id = o.customer_id
        LEFT JOIN LIVE.crm_summary          crm ON c.customer_id = crm.customer_id
    """)


@dlt.table(
    name="inventory_health",
    comment="SKU-level inventory health with days of supply and reorder status as of latest date."
)
def gold_inventory_health():
    return spark.sql("""
        SELECT
            store_id,
            sku_id,
            inventory_on_hand,
            ROUND(avg_daily_demand_7d, 1) AS avg_daily_demand_7d,
            ROUND(inventory_on_hand / NULLIF(avg_daily_demand_7d, 0), 1) AS days_of_supply,
            CASE
                WHEN inventory_on_hand / NULLIF(avg_daily_demand_7d, 0) < 3 THEN 'REORDER NOW'
                WHEN inventory_on_hand / NULLIF(avg_daily_demand_7d, 0) < 7 THEN 'WATCH'
                ELSE 'OK'
            END AS inventory_status,
            txn_date AS signal_date
        FROM LIVE.inventory
        WHERE txn_date = (SELECT MAX(txn_date) FROM LIVE.inventory)
    """)


@dlt.table(
    name="store_staffing_summary",
    comment="Labor gaps and headcount coverage by store and role."
)
def gold_staffing_summary():
    return spark.sql("""
        SELECT
            st.store_id,
            s.region,
            st.role,
            st.current_headcount,
            st.budgeted_headcount,
            (st.budgeted_headcount - st.current_headcount) AS headcount_gap,
            st.annual_labor_cost,
            CASE
                WHEN st.current_headcount < st.budgeted_headcount THEN 'UNDERSTAFFED'
                ELSE 'OK'
            END AS staffing_status
        FROM LIVE.staffing_raw st
        JOIN retail_demo.silver.stores s ON st.store_id = s.store_id
    """)
