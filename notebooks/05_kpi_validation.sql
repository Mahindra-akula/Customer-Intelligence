-- Databricks notebook source
-- 05_kpi_validation.sql
-- Sanity checks across all gold tables — run after pipeline + model notebooks

-- COMMAND ----------
-- Row counts per layer
SELECT 'bronze.customers_raw'    AS tbl, COUNT(*) AS rows FROM retail_demo.bronze.customers_raw
UNION ALL
SELECT 'bronze.orders_raw',               COUNT(*)         FROM retail_demo.bronze.orders_raw
UNION ALL
SELECT 'bronze.inventory_raw',            COUNT(*)         FROM retail_demo.bronze.inventory_raw
UNION ALL
SELECT 'bronze.crm_events_raw',           COUNT(*)         FROM retail_demo.bronze.crm_events_raw
UNION ALL
SELECT 'bronze.staffing_raw',             COUNT(*)         FROM retail_demo.bronze.staffing_raw
UNION ALL
SELECT 'silver.customers',                COUNT(*)         FROM retail_demo.silver.customers
UNION ALL
SELECT 'silver.orders',                   COUNT(*)         FROM retail_demo.silver.orders
UNION ALL
SELECT 'silver.inventory',                COUNT(*)         FROM retail_demo.silver.inventory
UNION ALL
SELECT 'silver.crm_summary',              COUNT(*)         FROM retail_demo.silver.crm_summary
UNION ALL
SELECT 'gold.customer_360',               COUNT(*)         FROM retail_demo.gold.customer_360
UNION ALL
SELECT 'gold.churn_scores',               COUNT(*)         FROM retail_demo.gold.churn_scores
UNION ALL
SELECT 'gold.inventory_health',           COUNT(*)         FROM retail_demo.gold.inventory_health
UNION ALL
SELECT 'gold.demand_forecast',            COUNT(*)         FROM retail_demo.gold.demand_forecast
UNION ALL
SELECT 'gold.store_staffing_summary',     COUNT(*)         FROM retail_demo.gold.store_staffing_summary
ORDER BY tbl;

-- COMMAND ----------
-- Churn score distribution
SELECT risk_tier, COUNT(*) AS customers,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM retail_demo.gold.churn_scores
GROUP BY risk_tier
ORDER BY risk_tier;

-- COMMAND ----------
-- Top 10 customers at highest churn risk
SELECT customer_id, customer_name, region, segment, recency_days,
       order_count_90d, ROUND(churn_prob, 3) AS churn_prob, risk_tier
FROM retail_demo.gold.churn_scores
WHERE risk_tier = 'High'
ORDER BY churn_prob DESC
LIMIT 10;

-- COMMAND ----------
-- Revenue at risk (High churn customers × avg spend)
SELECT
  ROUND(SUM(c360.total_spend_90d / 90 * 30), 0) AS monthly_revenue_at_risk,
  COUNT(*) AS high_risk_customers
FROM retail_demo.gold.churn_scores cs
JOIN retail_demo.gold.customer_360 c360 USING (customer_id)
WHERE cs.risk_tier = 'High';

-- COMMAND ----------
-- Inventory alerts — REORDER NOW
SELECT store_id, sku_id, inventory_on_hand, days_of_supply, inventory_status
FROM retail_demo.gold.inventory_health
WHERE inventory_status = 'REORDER NOW'
ORDER BY days_of_supply ASC
LIMIT 20;

-- COMMAND ----------
-- Demand forecast — top moving SKUs
SELECT sku_id, sku_name, category, demand_7d_avg, trend, predicted_units_7d
FROM retail_demo.gold.demand_forecast
ORDER BY demand_7d_avg DESC
LIMIT 10;

-- COMMAND ----------
-- Staffing gaps by store
SELECT store_id, region, role, current_headcount, budgeted_headcount,
       headcount_gap, staffing_status
FROM retail_demo.gold.store_staffing_summary
WHERE staffing_status = 'UNDERSTAFFED'
ORDER BY headcount_gap DESC;
