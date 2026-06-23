# IMPLEMENTATION PROMPT — Retail Customer Intelligence on Databricks
## SA Panel Interview · 4h Build + 1h Demo

## Mission
Build a working Databricks prototype that solves a mid-sized retailer's inability to make fast, data-driven decisions. The four problems: scattered data with no single source of truth, gut-instinct decisions on inventory/staffing/churn/risk, no forecasting infrastructure, and untapped accumulated knowledge.

The demo must land with three distinct personas in 60 minutes:
- **Business Leader** — sees the revenue at risk number and the customer churn risk
- **CTO** — sees medallion lineage, Unity Catalog governance, one-workspace answer
- **VP of Engineering** — sees the ML model output, live API, and RAG assistant working

> "Every exec meeting starts with a debate about whose numbers are right. This platform ends that debate — one catalog, one query, one answer."

---

## Workspace
| Setting | Value |
|---------|-------|
| Host | `https://dbc-eaeac0c1-f644.cloud.databricks.com` |
| Profile | `DEFAULT` |
| Catalog | `retail_demo` ← already exists, do NOT recreate |
| DLT Target Schema | `retail_data` ← single schema, Free Edition constraint |
| Bronze/Silver manual tables | `retail_demo.bronze.*`, `retail_demo.silver.*` |
| Gold (DLT output) | `retail_demo.retail_data.*` |
| Volume | `/Volumes/retail_demo/bronze/raw_data/` |
| SQL Warehouse | `4e7b8de25b26878f` |
| Compute | **Serverless only** — no classic clusters, no node type pinning |
| Table refs | Always three-part: `catalog.schema.table` |

---

## Critical Rules (Carry These Into Every File)

### Free Edition Constraints
- **Never** add `environment_key`, `environments:`, or `client: "1"` to any DAB resource → causes `INTERNAL_ERROR`
- Serverless compute is inferred automatically in job and pipeline YAML — do not specify it manually

### DLT / Lakeflow Pipelines — Single Schema Rule
- DLT can only write to **one target schema** per pipeline in Free Edition
- This pipeline targets `retail_demo.retail_data` — ALL DLT-managed tables land there
- Bronze/Silver tables written by the data gen notebook (`retail_demo.bronze.*`, `retail_demo.silver.*`) are NOT DLT-managed — DLT reads them via full three-part names
- The architecture diagram shows conceptual bronze/silver/gold layers — physically they coexist in `retail_demo.retail_data` for DLT-produced tables
- `main.py` references gold tables as `retail_demo.retail_data.customer_360`, `retail_demo.retail_data.churn_scores`, etc.

### Databricks App Auth
- Use **`databricks-sdk`** only — NOT `databricks-sql-connector`
- `databricks-sql-connector` ignores the injected token and tries OAuth browser flow → fails with "no free port"
- `WorkspaceClient()` auto-reads `DATABRICKS_HOST` + `DATABRICKS_TOKEN` injected by the Apps platform
- All values from `statement_execution` come back as **strings** — always cast:
  - `int(float(x))` for `ROUND()` / `SUM()` results (e.g., `'4350213.0'` → fails with plain `int()`)
  - `int(x)` for `COUNT(*)` results
  - `float(x)` for percentages and decimals
  - `str(x)` for dates

### App Service Principal Permissions
- The app creates its own service principal automatically on first deploy
- Get its UUID from `oauth2_app_client_id` field — NOT the display name
- Grant access after the first `bundle run` — UUID is stable across redeploys

### React + Vite Frontend
- Build output goes to `src/app/static/` — **only this directory is deployed**
- `node_modules/` is excluded by `.databricksignore` — verify this exists before first `bundle deploy`
- FastAPI mounts `/assets` as StaticFiles, then catch-all returns `index.html`
- **Always `npm run build` before `bundle deploy`** after any frontend change

### Demo Performance (Non-Negotiable)
- Backend: **1-hour in-memory cache** on all GET endpoints — warehouse queries take 2–5s cold; cached they're instant during demo
- Frontend: **lift all `fetch()` calls to `App.jsx`** in a single `useEffect([], [])` — all data loaded once at mount, passed as props
- Frontend: **`display:none/block`** tab switching — NOT `{active === 'x' && <Component/>}` — keeps all components mounted, preserves iframe and chat state

---

## Project Layout
```
ADB-Presentation-Final/
├── databricks.yml                      ← DAB root, targets dev workspace
├── .databricksignore                   ← CRITICAL: excludes node_modules + .venv
├── config/
│   └── pipeline_config.py             ← shared constants (N_STORES=10, N_CUSTOMERS=100)
├── data/
│   └── 00_synthetic_data_gen.py       ← creates schemas/volume + 4 source tables
├── pipelines/
│   └── 01_dlt_pipeline.py             ← DLT: reads bronze/silver → writes to retail_data
├── notebooks/
│   ├── 02_churn_model.py              ← XGBoost + MLflow → retail_data.churn_scores
│   ├── 03_demand_forecast.py          ← rolling 7d → retail_data.demand_forecast
│   ├── 04_rag_setup.py                ← Vector Search index + DBRX RAG chain
│   └── 05_kpi_validation.sql          ← row counts + sanity checks
├── resources/
│   ├── retail_demo_app.yml            ← Databricks App resource
│   └── retail_demo_pipeline.yml       ← DLT pipeline resource (target: retail_data)
└── src/app/
    ├── main.py                        ← FastAPI: 7 routes + 1-hour cache
    ├── app.yaml                       ← uvicorn command + WAREHOUSE_ID + email env vars
    ├── requirements.txt               ← fastapi uvicorn[standard] databricks-sdk (only these 3)
    ├── static/                        ← React build output (commit this, deploy this)
    └── frontend/                      ← React source (NOT deployed, excluded by .databricksignore)
        ├── index.html
        ├── package.json
        ├── vite.config.js
        └── src/
            ├── main.jsx
            ├── App.jsx                ← 4-tab nav + data lifting + display:none switching
            └── components/
                ├── Executive.jsx      ← KPI scorecards + churn donut + narrative
                ├── ChurnRisk.jsx      ← at-risk table + regional bar + segment chart
                ├── GenAI.jsx          ← chat interface + sidebar suggestions
                └── Architecture.jsx   ← 4-layer flow diagram (updates from platform-stats)
```

---

## Data Model

### Source Tables (written by data gen — NOT DLT-managed)
| Table | Schema | Rows | Source Mock |
|-------|--------|------|-------------|
| `customers_raw` | `bronze` | 1,000 | Postgres |
| `orders_raw` | `bronze` | ~4,500 | Postgres |
| `inventory_raw` | `bronze` | 4,000 | MySQL |
| `crm_events_raw` | `bronze` | ~2,000 | Salesforce CSV |
| `staffing_raw` | `bronze` | 40 | HR CSV |
| `stores` | `silver` | 10 | Dimension |
| `skus` | `silver` | 20 | Dimension |

### DLT-Managed Tables (all in `retail_demo.retail_data`)
| Table | Layer concept | Key content |
|-------|--------------|-------------|
| `customers_raw` | Bronze passthrough | DLT lineage wrapper |
| `orders_raw` | Bronze passthrough | DLT lineage wrapper |
| `inventory_raw` | Bronze passthrough | DLT lineage wrapper |
| `crm_events_raw` | Bronze passthrough | DLT lineage wrapper |
| `customers` | Silver | Cleaned + typed |
| `orders` | Silver | Parsed dates + return flag |
| `inventory` | Silver | Deduped + 7d rolling demand |
| `crm_summary` | Silver | Per-customer event counts |
| `customer_360` | **Gold — CORE ENTITY** | Unified profile + churn features |
| `inventory_health` | Gold | Days of supply + REORDER status |
| `store_staffing_summary` | Gold | Labor gaps per store/role |

### ML / GenAI Output Tables (written by notebooks, referenced by app)
| Table | Written by | Key columns |
|-------|-----------|-------------|
| `retail_demo.gold.churn_scores` | `02_churn_model.py` | `customer_id`, `churn_prob`, `risk_tier` |
| `retail_demo.gold.demand_forecast` | `03_demand_forecast.py` | `sku_id`, `demand_7d_avg`, `trend`, `predicted_units_7d` |
| `retail_demo.gold.rag_documents` | `04_rag_setup.py` | `doc_id`, `document` (for Vector Search) |

> **Note:** `main.py` queries churn/demand/RAG tables from `retail_demo.gold.*` and DLT tables from `retail_demo.retail_data.*`. Update `GOLD` env var in `app.yaml` accordingly, or use explicit three-part names in each query.

---

## Build Steps (Execute In This Order)

### Step 1 · Verify .databricksignore Exists
```
src/app/frontend/node_modules/
src/app/frontend/src/
src/app/frontend/public/
src/app/frontend/package.json
src/app/frontend/package-lock.json
src/app/frontend/vite.config.js
src/app/frontend/index.html
.venv/
```
**Do this before any `bundle deploy` or node_modules will upload (57MB) and stall deployment.**

---

### Step 2 · Validate DAB Config
```bash
databricks bundle validate --profile DEFAULT
```
Should return: `Bundle configuration is valid.`

If you see `INTERNAL_ERROR` on any resource, check for `environment_key`, `environments:`, or `client: "1"` — remove them.

---

### Step 3 · Deploy Bundle Resources
```bash
databricks bundle deploy --auto-approve --profile DEFAULT
```
This deploys: DLT pipeline definition + App resource definition to workspace.
Does NOT run anything yet.

---

### Step 4 · Run Data Generation
Open `data/00_synthetic_data_gen.py` in the workspace and run all cells.

OR if you added a job resource:
```bash
databricks bundle run data_gen_job --profile DEFAULT
```

**Verify after:**
```sql
SELECT 'bronze.customers_raw', COUNT(*) FROM retail_demo.bronze.customers_raw
UNION ALL SELECT 'bronze.orders_raw',    COUNT(*) FROM retail_demo.bronze.orders_raw
UNION ALL SELECT 'bronze.inventory_raw', COUNT(*) FROM retail_demo.bronze.inventory_raw
UNION ALL SELECT 'silver.stores',        COUNT(*) FROM retail_demo.silver.stores
UNION ALL SELECT 'silver.skus',          COUNT(*) FROM retail_demo.silver.skus;
-- Expected: 1000, ~4500, 4000, 10, 20
```

---

### Step 5 · Run DLT Pipeline
```bash
databricks bundle run retail_demo_pipeline --profile DEFAULT
```
Pipeline runs in background (~5–8 min on serverless). While it runs, do Steps 6 and 7.

**Verify after (run in SQL Editor):**
```sql
SELECT COUNT(*) FROM retail_demo.retail_data.customer_360;
-- Expected: 1,000
SELECT COUNT(*) FROM retail_demo.retail_data.inventory_health;
-- Expected: 200
```

---

### Step 6 · Run Churn Model (notebook 02)
Open `notebooks/02_churn_model.py` in workspace, run all cells.

**Verify:**
```sql
SELECT risk_tier, COUNT(*) FROM retail_demo.gold.churn_scores GROUP BY 1;
-- Expected: High ~300, Medium ~350, Low ~350
```

---

### Step 7 · Run Demand Forecast (notebook 03)
Open `notebooks/03_demand_forecast.py`, run all cells.

**Verify:**
```sql
SELECT sku_id, trend, demand_7d_avg FROM retail_demo.gold.demand_forecast LIMIT 5;
```

---

### Step 8 · RAG Setup (notebook 04 — optional for time-constrained build)
Open `notebooks/04_rag_setup.py`, run cells for Steps 1-2 (document corpus + CDF).
Vector Search endpoint creation (Step 3) takes ~10 min — start it and let it run.

If Vector Search is not ready for demo, the `/api/chat` endpoint falls back to SQL-grounded context + DBRX — this still demos well.

---

### Step 9 · Build React Frontend
```bash
cd src/app/frontend
npm install
npm run build
cd ../../..
```
Output lands in `src/app/static/`. This is what gets deployed to Databricks.

**Commit `src/app/static/` to git** before deploy — the bundle syncs this directory to the workspace.

---

### Step 10 · Start the App
```bash
databricks bundle run retail_demo_app --profile DEFAULT
```

Check logs:
```bash
databricks apps logs retail-demo-interview --profile DEFAULT
```

Look for:
```
[SYSTEM] Starting app with command: uvicorn main:app --host 0.0.0.0 --port 8000
[APP]    Uvicorn running on http://0.0.0.0:8000
[SYSTEM] Deployment successful
```

---

### Step 11 · Grant App Service Principal Permissions
Get the SP UUID:
```bash
databricks apps get retail-demo-interview --profile DEFAULT | python -c "import sys,json; print(json.load(sys.stdin)['oauth2_app_client_id'])"
```

Then run in a SQL worksheet (replace `<sp-uuid>`):
```sql
GRANT USE CATALOG ON CATALOG retail_demo TO `<sp-uuid>`;
GRANT USE SCHEMA ON SCHEMA retail_demo.bronze      TO `<sp-uuid>`;
GRANT USE SCHEMA ON SCHEMA retail_demo.silver      TO `<sp-uuid>`;
GRANT USE SCHEMA ON SCHEMA retail_demo.gold        TO `<sp-uuid>`;
GRANT USE SCHEMA ON SCHEMA retail_demo.retail_data TO `<sp-uuid>`;
GRANT SELECT ON SCHEMA retail_demo.bronze      TO `<sp-uuid>`;
GRANT SELECT ON SCHEMA retail_demo.silver      TO `<sp-uuid>`;
GRANT SELECT ON SCHEMA retail_demo.gold        TO `<sp-uuid>`;
GRANT SELECT ON SCHEMA retail_demo.retail_data TO `<sp-uuid>`;
```

Restart the app to pick up permissions:
```bash
databricks bundle run retail_demo_app --profile DEFAULT
```

---

### Step 12 · Verify All 4 Tabs
Open the app URL in browser. Check each tab:
- **Executive Overview** → KPI cards load with numbers (not "Loading...")
- **Churn Risk Center** → table shows 25 rows, regional bar chart renders
- **RetailAdvisor AI** → send a message, response comes back within 5s
- **Architecture** → diagram loads, row count shows at top

---

## FastAPI Routes Reference

| Route | Method | Source table(s) | What it returns |
|-------|--------|----------------|-----------------|
| `/api/summary` | GET | `retail_data.customer_360`, `gold.churn_scores`, `retail_data.inventory_health` | KPIs: churn rate, revenue at risk, customer count |
| `/api/churn-scores` | GET | `gold.churn_scores` | Top 25 high-risk customers |
| `/api/regional-churn` | GET | `gold.churn_scores` | Churn tier count by region (pivot) |
| `/api/churn-by-segment` | GET | `gold.churn_scores` | High-risk % by customer segment |
| `/api/demand-forecast` | GET | `gold.demand_forecast` | Top 20 SKUs with trend |
| `/api/inventory-alerts` | GET | `retail_data.inventory_health`, `silver.stores` | REORDER NOW items |
| `/api/platform-stats` | GET | All 14 tables | Row counts per table + last updated |
| `/api/chat` | POST `{query: str}` | `gold.churn_scores`, `retail_data.inventory_health`, `gold.demand_forecast` | RAG answer from DBRX |

---

## Time Budget (4-Hour Build)

| # | Task | Est. Time |
|---|------|-----------|
| 1 | Validate bundle + deploy resources | 5 min |
| 2 | Run data generation notebook | 5 min |
| 3 | Start DLT pipeline (background) | Kick off, ~8 min to complete |
| 4 | Run churn model notebook | 5 min |
| 5 | Run demand forecast notebook | 3 min |
| 6 | Start RAG setup (background — Vector Search takes 10 min) | Kick off |
| 7 | `npm install && npm run build` | 3 min |
| 8 | `bundle run retail_demo_app` | 3 min |
| 9 | Get SP UUID + run GRANT statements | 5 min |
| 10 | Restart app + verify all 4 tabs | 5 min |
| 11 | Run KPI validation notebook | 5 min |
| 12 | Create AI/BI Lakeview dashboard (optional for Executive tab iframe) | 20 min |
| 13 | Rehearse demo narrative — all 4 tabs | 20 min |
| **Total active** | | **~79 min** |
| **Buffer / rework** | | ~41 min |
| **Total** | | **~2 hours** |

> DLT and Vector Search run in background. While they run, do the React build + app deploy. Everything converges by the time you need to demo.

---

## Demo Script Cues (4-Layer Narrative)

| Persona | Moment | Line |
|---------|--------|------|
| **Business Leader** | Executive KPI cards | "Every exec meeting starts with a debate about whose numbers are right. This number — $X monthly revenue at risk — comes from one table. No debate." |
| **Business Leader** | Churn risk tier donut | "These are your customers, scored by ML this morning. The 30% in red haven't ordered in over 30 days. Without this, you find out when they cancel." |
| **Business Leader** | "Reach Out" button | "One click adds this customer to a retention workflow. No CRM integration needed for the demo — in production, this fires a Salesforce task." |
| **CTO** | Architecture tab | "Four layers, one workspace. Snowflake needs a separate BI tool, separate governance layer, separate orchestrator. This is Databricks." |
| **CTO** | Architecture — Unity Catalog badge | "Every table has lineage. Click any gold table in Unity Catalog — you see exactly which bronze record it came from. That's the CTO's compliance answer." |
| **CTO** | DLT pipeline | "DLT switches from batch to streaming with one line change — `spark.read` to `spark.readStream` in the bronze layer. No pipeline rewrite." |
| **VP Engineering** | Churn Risk table | "XGBoost trained on 1,000 customers in under 30 seconds. ROC-AUC logged to MLflow. Model registered in Unity Catalog. Retrain is one notebook run." |
| **VP Engineering** | Regional stacked bar | "Five regions, three risk tiers — this pivot came from one SQL GROUP BY with no BI tool in the middle. FastAPI returns it in under 50ms from cache." |
| **VP Engineering** | RetailAdvisor AI tab | "This isn't ChatGPT hallucinating. The answer is grounded in live SQL — it pulled the churn count, the inventory alert count, and the regional breakdown before generating one word." |
| **All** | Architecture tab → this app | "One URL. Business Leader, CTO, VP Engineering each see their view. No separate tools, no separate logins, no connectors to maintain." |

---

## Troubleshooting

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `INTERNAL_ERROR` on pipeline/job run | `environment_key` / `environments:` / `client:"1"` in YAML | Remove those fields — Free Edition infers serverless |
| App 500 on all routes — "no free port" | `databricks-sql-connector` in requirements.txt | Replace with `databricks-sdk` only |
| `ValueError: invalid literal for int()` | `ROUND()`/`SUM()` returns `'4350213.0'` as string | Use `int(float(x))` — never bare `int(x)` on SQL aggregates |
| Deployment stuck "Preparing source code" | `node_modules` uploaded before `.databricksignore` existed | `databricks workspace delete --recursive .../frontend` then redeploy |
| App SP permission denied on queries | SP not granted Unity Catalog access | Run GRANT statements using `oauth2_app_client_id` UUID |
| SP GRANT fails "principal not found" | Used display name instead of UUID | Get UUID via `databricks apps get ... \| python -c "...oauth2_app_client_id..."` |
| `gold.churn_scores` not found | Churn model notebook not yet run | Run `02_churn_model.py` before starting app |
| `retail_data.customer_360` not found | DLT pipeline not yet completed | Wait for pipeline to finish; check pipeline UI |
| 2-second reload on tab switch | Components unmounting on each click | Use `display:none/block` in App.jsx — not `{active === 'x' && <Component/>}` |
| Chat returns "Unable to generate answer" | DBRX endpoint not available or context empty | Check if DBRX serving endpoint is active; SQL fallback text is still demo-able |
| App shows old version after redeploy | Static files cached | `databricks bundle run retail_demo_app` to restart; hard refresh browser |
| All API routes return 401 via curl | Databricks Apps requires browser OAuth | Expected — test in browser only, not curl |

---

## Key Commands Cheat Sheet
```bash
# Validate bundle
databricks bundle validate --profile DEFAULT

# Deploy all resources
databricks bundle deploy --auto-approve --profile DEFAULT

# Run DLT pipeline
databricks bundle run retail_demo_pipeline --profile DEFAULT

# Start/restart app
databricks bundle run retail_demo_app --profile DEFAULT

# Get app logs
databricks apps logs retail-demo-interview --profile DEFAULT

# Get SP UUID for grants
databricks apps get retail-demo-interview --profile DEFAULT | python -c "import sys,json; print(json.load(sys.stdin)['oauth2_app_client_id'])"

# Build React (run before every deploy with frontend changes)
cd src/app/frontend && npm install && npm run build && cd ../../..
```
