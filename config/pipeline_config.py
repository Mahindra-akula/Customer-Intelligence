# Databricks notebook source
# pipeline_config.py — shared constants for all notebooks
# Usage: %run ../config/pipeline_config

CATALOG        = "retail_demo"
BRONZE_SCHEMA  = "bronze"
SILVER_SCHEMA  = "silver"
GOLD_SCHEMA    = "gold"
PIPELINE_SCHEMA = "retail_data"   # DLT target schema (customer_360, inventory_health, etc.)
VOLUME_PATH    = f"/Volumes/{CATALOG}/{BRONZE_SCHEMA}/raw_data"

N_STORES              = 10    # 10 stores across 5 regions
N_CUSTOMERS_PER_STORE = 100   # 1,000 customers total
N_SKUS                = 20    # high-velocity SKUs
N_DAYS                = 20    # 20-day rolling window

CHURN_LOOKBACK_DAYS   = 90    # feature window
CHURN_TARGET_DAYS     = 30    # no order in 30d = churned
REORDER_DAYS          = 3     # days_of_supply < 3 → REORDER NOW
WATCH_DAYS            = 7     # days_of_supply < 7 → WATCH

MODEL_NAME = "retail_demo_churn"
