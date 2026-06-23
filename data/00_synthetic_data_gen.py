# Databricks notebook source
# 00_synthetic_data_gen.py
# Generates synthetic retail data across 5 source tables (mocking Postgres + MySQL + SaaS CSVs)
# Scale: 10 stores × 100 customers × 20 SKUs × 20 days — fast, stays under 1,000 records/store

# COMMAND ----------
%run ../config/pipeline_config

# COMMAND ----------
from pyspark.sql import functions as F
import datetime

# ── Workspace setup ────────────────────────────────────────────────────────────
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{BRONZE_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SILVER_SCHEMA}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{GOLD_SCHEMA}")
spark.sql(f"CREATE VOLUME  IF NOT EXISTS {CATALOG}.{BRONZE_SCHEMA}.raw_data")
print("Catalog, schemas, and volume ready.")

# COMMAND ----------
# ── SOURCE 1 (Postgres mock): stores ──────────────────────────────────────────
regions = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
states_by_region = {
    "Northeast": ["NY", "MA", "CT", "NJ", "PA"],
    "Southeast": ["FL", "GA", "NC", "SC", "VA"],
    "Midwest":   ["IL", "OH", "MI", "IN", "WI"],
    "Southwest": ["TX", "AZ", "NM", "NV", "OK"],
    "West":      ["CA", "WA", "OR", "CO", "UT"],
}

stores_data = [
    (i + 1, f"STORE_{i+1:04d}", regions[i % 5], states_by_region[regions[i % 5]][i % 5])
    for i in range(N_STORES)
]
stores_df = spark.createDataFrame(stores_data, ["store_id", "store_name", "region", "state"])
stores_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{SILVER_SCHEMA}.stores")
print(f"stores: {stores_df.count()} rows")

# COMMAND ----------
# ── SOURCE 1 (Postgres mock): customers ───────────────────────────────────────
segments   = ["Premium", "Standard", "Budget"]
channels   = ["Online", "In-Store", "Mobile"]
customers_data = []
for store_i in range(N_STORES):
    store_id = store_i + 1
    for c in range(N_CUSTOMERS_PER_STORE):
        cust_id  = store_i * N_CUSTOMERS_PER_STORE + c + 1
        age      = 22 + (cust_id % 50)
        segment  = segments[cust_id % 3]
        channel  = channels[cust_id % 3]
        join_day = (cust_id % 365)
        customers_data.append((cust_id, f"CUST_{cust_id:05d}", store_id, age, segment, channel, join_day))

customers_df = spark.createDataFrame(
    customers_data,
    ["customer_id", "customer_name", "store_id", "age", "segment", "preferred_channel", "days_since_join"]
)
customers_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{BRONZE_SCHEMA}.customers_raw")
print(f"customers_raw: {customers_df.count()} rows")

# COMMAND ----------
# ── SOURCE 1 (Postgres mock): orders ──────────────────────────────────────────
end_date   = datetime.date.today()
start_date = end_date - datetime.timedelta(days=CHURN_LOOKBACK_DAYS - 1)

orders_data = []
order_id = 1
for cust_i, (cust_id, cust_name, store_id, age, segment, channel, join_day) in enumerate(customers_data):
    # 70% of customers have recent orders; 30% are "churned" (no orders in last 30d)
    is_churned = (cust_id % 10) >= 7
    max_order_day = CHURN_LOOKBACK_DAYS if not is_churned else CHURN_LOOKBACK_DAYS - CHURN_TARGET_DAYS - 1
    num_orders = 2 + (cust_id % 6)  # 2-7 orders per customer
    for o in range(num_orders):
        days_ago  = (o * (max_order_day // num_orders)) + 1
        order_date = end_date - datetime.timedelta(days=days_ago)
        base_value = 25 + (cust_id % 200)
        is_returned = (order_id % 8 == 0)
        orders_data.append((
            order_id, cust_id, store_id, str(order_date),
            float(base_value), is_returned
        ))
        order_id += 1

orders_df = spark.createDataFrame(
    orders_data,
    ["order_id", "customer_id", "store_id", "order_date", "order_value", "is_returned"]
)
orders_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{BRONZE_SCHEMA}.orders_raw")
print(f"orders_raw: {orders_df.count()} rows")

# COMMAND ----------
# ── SOURCE 2 (MySQL mock): products / SKUs ────────────────────────────────────
categories = ["beverages", "snacks", "dairy", "produce", "frozen",
              "personal_care", "household", "bakery", "electronics", "apparel"]
avg_prices = {
    "beverages": 4.99, "snacks": 2.49, "dairy": 3.99, "produce": 2.99,
    "frozen": 5.99, "personal_care": 6.99, "household": 7.49,
    "bakery": 3.49, "electronics": 49.99, "apparel": 29.99,
}
skus_data = [
    (i + 1, f"SKU_{i+1:04d}", categories[i % 10], avg_prices[categories[i % 10]])
    for i in range(N_SKUS)
]
skus_df = spark.createDataFrame(skus_data, ["sku_id", "sku_name", "category", "avg_unit_price"])
skus_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{SILVER_SCHEMA}.skus")
print(f"skus: {skus_df.count()} rows")

# COMMAND ----------
# ── SOURCE 2 (MySQL mock): inventory ──────────────────────────────────────────
inv_end   = datetime.date.today()
inv_start = inv_end - datetime.timedelta(days=N_DAYS - 1)

dates_df  = spark.sql(f"""
    SELECT explode(sequence(DATE('{inv_start}'), DATE('{inv_end}'), INTERVAL 1 DAY)) AS txn_date
""")
store_ids = spark.table(f"{CATALOG}.{SILVER_SCHEMA}.stores").select("store_id")
sku_ids   = spark.table(f"{CATALOG}.{SILVER_SCHEMA}.skus").select("sku_id", "avg_unit_price")

inventory_raw = (
    dates_df
    .crossJoin(store_ids)
    .crossJoin(sku_ids)
    .withColumn("day_of_week", F.dayofweek("txn_date"))
    .withColumn("base_qty",    (F.rand(seed=42) * 30 + 5).cast("int"))
    .withColumn("seasonal_mult",
        F.when(F.col("day_of_week").isin(1, 7), 1.2)
         .when(F.col("day_of_week") == 2, 0.85)
         .otherwise(1.0))
    .withColumn("is_stockout",       F.rand(seed=99) < 0.10)
    .withColumn("qty_sold",
        F.when(F.col("is_stockout"), 0)
         .otherwise((F.col("base_qty") * F.col("seasonal_mult")).cast("int")))
    .withColumn("inventory_on_hand",
        F.when(F.col("is_stockout"), 0)
         .otherwise((F.rand(seed=7) * 80 + 10).cast("int")))
    .withColumn("unit_price", F.col("avg_unit_price"))
    .select("store_id", "sku_id", "txn_date", "qty_sold", "unit_price", "inventory_on_hand")
)
inventory_raw.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{BRONZE_SCHEMA}.inventory_raw")
print(f"inventory_raw: {inventory_raw.count()} rows")

# COMMAND ----------
# ── SOURCE 3 (SaaS CSV mock): CRM / support events ────────────────────────────
crm_types    = ["complaint", "inquiry", "return_request", "loyalty_redemption", "feedback"]
crm_data     = []
for cust_i, (cust_id, *rest) in enumerate(customers_data):
    num_events = 1 + (cust_id % 3)
    for e in range(num_events):
        days_ago   = (e * 20) + (cust_id % 15)
        event_date = end_date - datetime.timedelta(days=days_ago)
        crm_data.append((
            cust_i * 3 + e + 1,
            cust_id,
            crm_types[(cust_id + e) % 5],
            str(event_date),
            f"Customer {cust_id} contacted regarding {crm_types[(cust_id + e) % 5]}."
        ))

crm_df = spark.createDataFrame(
    crm_data,
    ["event_id", "customer_id", "event_type", "event_date", "notes"]
)
crm_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{BRONZE_SCHEMA}.crm_events_raw")
print(f"crm_events_raw: {crm_df.count()} rows")

# COMMAND ----------
# ── SOURCE 4 (HR CSV mock): staffing ──────────────────────────────────────────
roles       = ["Store Manager", "Floor Associate", "Cashier", "Inventory Clerk"]
staffing_data = []
for store_id in range(1, N_STORES + 1):
    for role_i, role in enumerate(roles):
        headcount  = 2 + (store_id % 3)
        budgeted   = headcount + 1
        labor_cost = headcount * (35000 + role_i * 5000)
        staffing_data.append((store_id, role, headcount, budgeted, float(labor_cost)))

staffing_df = spark.createDataFrame(
    staffing_data,
    ["store_id", "role", "current_headcount", "budgeted_headcount", "annual_labor_cost"]
)
staffing_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{BRONZE_SCHEMA}.staffing_raw")
print(f"staffing_raw: {staffing_df.count()} rows")

# COMMAND ----------
print("Data generation complete.")
print(f"Catalog:  {CATALOG}")
print(f"Stores:   {N_STORES}")
print(f"Customers: {N_STORES * N_CUSTOMERS_PER_STORE:,}")
print(f"SKUs:     {N_SKUS}")
print(f"Inventory rows: {N_STORES * N_SKUS * N_DAYS:,}")
