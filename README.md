# Retail Customer Intelligence — Databricks Demo

A full-stack retail analytics platform built on Databricks, demonstrating how a regional grocery chain can move from reactive reporting to proactive, AI-driven decision-making.

---

## Use Case

A regional retailer with 10 stores and 1,000 customers faces three problems:

1. **Churn is invisible** — customers leave before anyone notices the signal
2. **Inventory is reactive** — stockouts are discovered on the shelf, not in the data
3. **Data is siloed** — CRM, POS, HR, and inventory live in separate systems; nobody trusts the numbers

This platform unifies all four data sources into a single certified Customer 360, runs ML to surface risk before it becomes loss, and gives every store manager and executive a live AI interface to ask questions in plain English.

**Live demo:** https://retail-demo-interview-7474655529260099.aws.databricksapps.com

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                             │
│   Postgres (CRM) · MySQL (Inventory) · Salesforce · HR System   │
└───────────────────────────┬─────────────────────────────────────┘
                            │  Auto Loader / JDBC
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Bronze Layer  (raw ingestion)                  │
│   customers_raw · inventory_raw · transactions_raw · hr_raw      │
│                    Delta Live Tables (DLT)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │  DLT — cleanse + join
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Silver Layer  (conformed)                      │
│   customer_360 · inventory · store_staffing_summary              │
│              Unity Catalog — retail_demo.retail_data             │
└───────────────────────────┬─────────────────────────────────────┘
                            │  DLT + ML Notebooks
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Gold Layer  (serving)                         │
│   churn_scores (XGBoost)  ·  demand_forecast (rolling avg)      │
│   inventory_health (rules) · store_staffing_summary             │
│              Unity Catalog — retail_demo.gold                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │  FastAPI + Databricks SDK
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Databricks App  (React + FastAPI)              │
│                                                                  │
│  Executive Overview  │  Churn Risk  │  Inventory  │  Staffing   │
│  RetailAdvisor AI    │  Genie Space │  Architecture              │
│                                                                  │
│     Llama 3.3 70B (DBRX fallback) · 1-hr in-memory cache        │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Ingestion | Delta Live Tables | Bronze → Silver pipeline with data quality checks |
| Storage | Delta Lake + Unity Catalog | Single governed catalog; column-level security |
| ML — Churn | XGBoost + MLflow | Scores all customers daily; registered in Unity Catalog |
| ML — Demand | Rolling average + trend | 7-day forward projection per SKU |
| Inventory Health | Rule-based (DLT) | Days-of-supply threshold → REORDER NOW / WATCH / OK |
| Serving | FastAPI + Databricks SDK | REST API over SQL warehouse; serverless compute |
| Frontend | React + Vite | Single-page app; data lifted to App.jsx, display:none tab switching |
| GenAI | Llama 3.3 70B Instruct | RetailAdvisor chatbot grounded on live retail data |
| Self-serve BI | Databricks Genie | NL queries over Customer 360 + Gold tables |
| Deployment | Databricks Asset Bundles | One-command deploy: `databricks bundle deploy && databricks bundle run retail_demo_app` |

---

## Repository Structure

```
├── config/
│   └── pipeline_config.py        # Catalog, schema, and model name constants
├── data/
│   └── 00_synthetic_data_gen.py  # Generates synthetic retail data into Unity Catalog volumes
├── pipelines/
│   └── 01_dlt_pipeline.py        # DLT pipeline: Bronze → Silver → Gold
├── notebooks/
│   ├── 02_churn_model.py         # XGBoost churn model — trains and registers to Unity Catalog
│   ├── 03_demand_forecast.py     # Rolling demand forecast — writes gold.demand_forecast
│   ├── 04_rag_setup.py           # Vector search / RAG setup (optional)
│   └── 05_kpi_validation.sql     # SQL validation queries for all Gold tables
├── src/app/
│   ├── main.py                   # FastAPI backend — all API endpoints
│   ├── app.yaml                  # Databricks App config (env vars, startup command)
│   ├── requirements.txt          # Python dependencies
│   ├── static/                   # Built React SPA (generated by npm run build)
│   └── frontend/
│       └── src/components/
│           ├── Executive.jsx     # KPIs, Top 5 Priorities, Genie iframe
│           ├── ChurnRisk.jsx     # Churn scores table + segment breakdown
│           ├── GenAI.jsx         # RetailAdvisor AI chat interface
│           └── Architecture.jsx  # Live data lineage view
├── resources/
│   ├── retail_demo_app.yml       # DAB resource: Databricks App
│   ├── retail_demo_pipeline.yml  # DAB resource: DLT pipeline
│   ├── ml_jobs.yml               # DAB resource: churn + forecast jobs
│   └── data_gen.job.yml          # DAB resource: synthetic data job
└── databricks.yml                # Databricks Asset Bundle root config
```

---

## Deploy

```bash
# 1. Build frontend
cd src/app/frontend && npm install && npm run build

# 2. Deploy everything (pipeline, jobs, app)
databricks bundle deploy

# 3. Run data generation + pipeline (first time only)
databricks bundle run data_gen_job
databricks bundle run churn_model_job
databricks bundle run demand_forecast_job

# 4. Start the app
databricks bundle run retail_demo_app
```

---

## Business Outcomes

| Metric | Value |
|--------|-------|
| High-risk customers identified | 74 (7.4% of base) |
| Monthly revenue at risk | $10,897 |
| Inventory alerts (REORDER NOW) | 132 SKU/store combos |
| Churn rate reduction (target) | 7.4% → 5.1% with proactive retention |
| Forecast error reduction | 20–30% vs manual planning |
| Infrastructure consolidation | CRM + DW + ML → one lakehouse |
