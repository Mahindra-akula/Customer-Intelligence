# Databricks notebook source
# 03_demand_forecast.py — Demand Forecast
# Computes rolling 7-day demand per SKU + 7-day forward projection
# Writes gold.demand_forecast — feeds inventory reorder decisions

# COMMAND ----------
%run ../config/pipeline_config

# COMMAND ----------
from pyspark.sql import functions as F, Window

# retail_data.inventory schema: store_id, sku_id, txn_date, qty_sold,
#   unit_price, inventory_on_hand, avg_daily_demand_7d, load_ts
inv = spark.table(f"{CATALOG}.{PIPELINE_SCHEMA}.inventory")

# Derive sku_name and category from sku_id (no separate SKU dimension table)
CATEGORIES = ["Produce", "Dairy", "Bakery", "Meat", "Beverages"]
inv = inv.withColumn(
    "sku_name", F.concat(F.lit("SKU-"), F.col("sku_id"))
).withColumn(
    "category", F.element_at(
        F.array([F.lit(c) for c in CATEGORIES]),
        (F.col("sku_id") % len(CATEGORIES) + 1).cast("int")
    )
)

# Per-SKU daily demand aggregated across all stores
sku_daily = (
    inv
    .groupBy("sku_id", "sku_name", "category", "txn_date")
    .agg(
        F.sum("qty_sold").alias("total_qty_sold"),
        F.avg("inventory_on_hand").alias("avg_inventory"),
        F.avg("unit_price").alias("avg_unit_price"),
    )
)

# Rolling 7-day and 14-day averages per SKU
w7  = Window.partitionBy("sku_id").orderBy("txn_date").rowsBetween(-6, 0)
w14 = Window.partitionBy("sku_id").orderBy("txn_date").rowsBetween(-13, 0)

sku_signals = (
    sku_daily
    .withColumn("demand_7d_avg",  F.round(F.avg("total_qty_sold").over(w7),  1))
    .withColumn("demand_14d_avg", F.round(F.avg("total_qty_sold").over(w14), 1))
)

# Latest day only — basis for forward projection
latest_date = sku_signals.agg(F.max("txn_date")).collect()[0][0]
latest = sku_signals.filter(F.col("txn_date") == latest_date)

forecast = (
    latest
    .withColumn("trend",
        F.when(F.col("demand_7d_avg") > F.col("demand_14d_avg") * 1.05, "UP")
         .when(F.col("demand_7d_avg") < F.col("demand_14d_avg") * 0.95, "DOWN")
         .otherwise("FLAT")
    )
    .withColumn("predicted_units_7d",
        F.round(F.col("demand_7d_avg") * 7, 0).cast("int")
    )
    .withColumn("confidence",
        F.when(F.col("trend") == "UP",   "High")
         .when(F.col("trend") == "DOWN", "Medium")
         .otherwise("High")
    )
    .select(
        "sku_id", "sku_name", "category",
        "demand_7d_avg", "demand_14d_avg",
        "trend", "predicted_units_7d", "confidence",
        F.col("txn_date").alias("signal_date"),
        F.round("avg_unit_price", 2).alias("avg_unit_price"),
    )
)

forecast.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.demand_forecast")
print(f"demand_forecast written: {forecast.count()} rows")

display(
    spark.table(f"{CATALOG}.{GOLD_SCHEMA}.demand_forecast")
    .orderBy(F.desc("demand_7d_avg"))
    .limit(10)
)
