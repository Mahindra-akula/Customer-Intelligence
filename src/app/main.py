import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

app = FastAPI()

WAREHOUSE_ID    = os.environ.get("WAREHOUSE_ID",    "4e7b8de25b26878f")
CATALOG         = os.environ.get("CATALOG",         "retail_demo")
PIPELINE        = os.environ.get("PIPELINE_SCHEMA", "retail_data")
GOLD            = os.environ.get("GOLD_SCHEMA",     "gold")
SILVER          = os.environ.get("SILVER_SCHEMA",   "silver")
GENIE_SPACE_ID  = os.environ.get("GENIE_SPACE_ID",  "")
CACHE_TTL       = 3600

_client = None
_cache: dict = {}


def get_client():
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def cached(key: str, fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    result = fn()
    _cache[key] = (now, result)
    return result


def query(sql_text: str) -> list[dict]:
    """Execute SQL via statement execution API.
    NOTE: All returned values are STRINGS — cast explicitly.
    Use int(float(x)) for ROUND/SUM; int(x) for COUNT; float(x) for decimals."""
    result = get_client().statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=sql_text,
        wait_timeout="50s",
    )
    if result.status.state != StatementState.SUCCEEDED:
        err = result.status.error
        raise RuntimeError(f"Query failed [{result.status.state}]: {err.message if err else 'unknown'}")
    cols = [col.name for col in result.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in (result.result.data_array or [])]


# ════════════════════════════════════════════════════════════════════════════════
# EXECUTIVE — KPI summary
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/summary")
def summary():
    return cached("summary", _summary)

def _summary():
    churn = query(f"""
        SELECT risk_tier, COUNT(*) AS cnt,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM {CATALOG}.{GOLD}.churn_scores
        GROUP BY risk_tier
        ORDER BY cnt DESC
    """)
    rev = query(f"""
        SELECT ROUND(SUM(c.total_spend_90d / 90 * 30), 0) AS monthly_rev_at_risk,
               COUNT(*) AS high_risk_count
        FROM {CATALOG}.{GOLD}.churn_scores cs
        JOIN {CATALOG}.{PIPELINE}.customer_360 c USING (customer_id)
        WHERE cs.risk_tier = 'High'
    """)
    totals = query(f"""
        SELECT COUNT(DISTINCT customer_id) AS total_customers,
               COUNT(DISTINCT store_id)   AS total_stores
        FROM {CATALOG}.{PIPELINE}.customer_360
    """)
    inv_alerts = query(f"""
        SELECT COUNT(*) AS reorder_count
        FROM {CATALOG}.{PIPELINE}.inventory_health
        WHERE inventory_status = 'REORDER NOW'
    """)
    high_pct = next((float(r["pct"]) for r in churn if r["risk_tier"] == "High"), 0)
    return {
        "churn_rate_pct":      high_pct,
        "revenue_at_risk":     int(float(rev[0]["monthly_rev_at_risk"] or 0)),
        "high_risk_customers": int(rev[0]["high_risk_count"] or 0),
        "total_customers":     int(totals[0]["total_customers"]),
        "total_stores":        int(totals[0]["total_stores"]),
        "inventory_alerts":    int(inv_alerts[0]["reorder_count"]),
        "risk_tiers": [
            {"tier": r["risk_tier"], "count": int(r["cnt"]), "pct": float(r["pct"])}
            for r in churn
        ],
    }


# ════════════════════════════════════════════════════════════════════════════════
# CHURN RISK — top at-risk customers + regional breakdown
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/churn-scores")
def churn_scores():
    return cached("churn-scores", _churn_scores)

def _churn_scores():
    return query(f"""
        SELECT cs.customer_id, cs.customer_name, cs.region, cs.segment,
               cs.recency_days, cs.order_count_90d,
               ROUND(cs.total_spend_90d, 2) AS total_spend_90d,
               ROUND(cs.churn_prob, 3)       AS churn_prob,
               cs.risk_tier
        FROM {CATALOG}.{GOLD}.churn_scores cs
        WHERE cs.risk_tier = 'High'
        ORDER BY cs.churn_prob DESC
        LIMIT 25
    """)


@app.get("/api/regional-churn")
def regional_churn():
    return cached("regional-churn", _regional_churn)

def _regional_churn():
    rows = query(f"""
        SELECT region, risk_tier, COUNT(*) AS cnt
        FROM {CATALOG}.{GOLD}.churn_scores
        GROUP BY region, risk_tier
        ORDER BY region
    """)
    pivot: dict = {}
    for r in rows:
        region = r["region"]
        if region not in pivot:
            pivot[region] = {"region": region, "High": 0, "Medium": 0, "Low": 0}
        pivot[region][r["risk_tier"]] = int(r["cnt"])
    return list(pivot.values())


@app.get("/api/churn-by-segment")
def churn_by_segment():
    return cached("churn-by-segment", _churn_by_segment)

def _churn_by_segment():
    return query(f"""
        SELECT segment,
               COUNT(*) AS total,
               SUM(CASE WHEN risk_tier = 'High' THEN 1 ELSE 0 END) AS high_risk,
               ROUND(SUM(CASE WHEN risk_tier = 'High' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS high_risk_pct
        FROM {CATALOG}.{GOLD}.churn_scores
        GROUP BY segment
        ORDER BY high_risk_pct DESC
    """)


# ════════════════════════════════════════════════════════════════════════════════
# DEMAND + INVENTORY
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/demand-forecast")
def demand_forecast():
    return cached("demand-forecast", _demand_forecast)

def _demand_forecast():
    return query(f"""
        SELECT sku_id, sku_name, category, trend,
               ROUND(demand_7d_avg, 1) AS demand_7d_avg,
               predicted_units_7d, confidence, avg_unit_price
        FROM {CATALOG}.{GOLD}.demand_forecast
        ORDER BY demand_7d_avg DESC
        LIMIT 20
    """)


@app.get("/api/inventory-alerts")
def inventory_alerts():
    return cached("inventory-alerts", _inventory_alerts)

def _inventory_alerts():
    return query(f"""
        SELECT ih.store_id, s.region, ih.sku_id,
               ih.inventory_on_hand,
               ROUND(ih.days_of_supply, 1) AS days_of_supply,
               ROUND(ih.avg_daily_demand_7d, 1) AS avg_daily_demand_7d,
               ih.inventory_status
        FROM {CATALOG}.{PIPELINE}.inventory_health ih
        JOIN {CATALOG}.{SILVER}.stores s USING (store_id)
        WHERE ih.inventory_status = 'REORDER NOW'
        ORDER BY ih.days_of_supply ASC
        LIMIT 25
    """)


# ════════════════════════════════════════════════════════════════════════════════
# PLATFORM STATS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/platform-stats")
def platform_stats():
    return cached("platform-stats", _platform_stats)

def _platform_stats():
    tables = [
        ("bronze.customers_raw",       "Bronze", "Postgres (mock)"),
        ("bronze.orders_raw",          "Bronze", "Postgres (mock)"),
        ("bronze.inventory_raw",       "Bronze", "MySQL (mock)"),
        ("bronze.crm_events_raw",      "Bronze", "Salesforce CSV (mock)"),
        ("bronze.staffing_raw",        "Bronze", "HR CSV (mock)"),
        (f"{PIPELINE}.customers",           "Silver", "DLT cleaned"),
        (f"{PIPELINE}.orders",              "Silver", "DLT cleaned"),
        (f"{PIPELINE}.inventory",           "Silver", "DLT + rolling demand"),
        (f"{PIPELINE}.crm_summary",         "Silver", "DLT aggregated"),
        (f"{PIPELINE}.customer_360",        "Gold",   "Core entity (DLT)"),
        (f"{GOLD}.churn_scores",            "Gold",   "XGBoost ML output"),
        (f"{PIPELINE}.inventory_health",    "Gold",   "Reorder signals (DLT)"),
        (f"{GOLD}.demand_forecast",         "Gold",   "Rolling forecast"),
        (f"{PIPELINE}.store_staffing_summary","Gold", "Labor gaps (DLT)"),
    ]
    result = []
    for tbl, layer, source in tables:
        try:
            rows = query(f"SELECT COUNT(*) AS cnt FROM {CATALOG}.{tbl}")
            result.append({"table": tbl, "layer": layer, "source": source, "rows": int(rows[0]["cnt"])})
        except Exception:
            result.append({"table": tbl, "layer": layer, "source": source, "rows": 0})
    last = query(f"SELECT MAX(updated_at) AS last_updated FROM {CATALOG}.{PIPELINE}.customer_360")
    return {"tables": result, "last_updated": str(last[0]["last_updated"])}


# ════════════════════════════════════════════════════════════════════════════════
# GENAI — RetailAdvisor chatbot (SQL-grounded, no Vector Search dependency)
# Falls back to Foundation Model API with context pulled from gold tables
# ════════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    q = req.query.strip().lower()

    # Pull relevant context from gold tables based on query intent
    context_parts = []

    try:
        # Always include executive KPIs
        kpis = query(f"""
            SELECT
                COUNT(*) AS total_customers,
                SUM(CASE WHEN risk_tier = 'High' THEN 1 ELSE 0 END) AS high_risk,
                ROUND(AVG(churn_prob) * 100, 1) AS avg_churn_pct
            FROM {CATALOG}.{GOLD}.churn_scores
        """)
        if kpis:
            r = kpis[0]
            context_parts.append(
                f"KPIs: {int(r['total_customers'])} total customers, "
                f"{int(r['high_risk'])} at high churn risk ({float(r['avg_churn_pct']):.1f}% avg churn probability)."
            )

        # Inventory context
        if any(word in q for word in ["inventory", "stock", "reorder", "supply", "sku"]):
            inv = query(f"""
                SELECT COUNT(*) AS cnt, ROUND(AVG(days_of_supply), 1) AS avg_dos
                FROM {CATALOG}.{PIPELINE}.inventory_health
                WHERE inventory_status = 'REORDER NOW'
            """)
            if inv:
                context_parts.append(
                    f"Inventory: {int(inv[0]['cnt'])} SKU/store combos need immediate reorder. "
                    f"Average days of supply remaining: {float(inv[0]['avg_dos']):.1f} days."
                )

        # Regional context — "store" must be a word boundary (avoid matching "understaffed")
        if any(f" {word} " in f" {q} " for word in ["region", "store", "stores", "location", "northeast", "west", "south", "midwest"]):
            regional = query(f"""
                SELECT region,
                       SUM(CASE WHEN risk_tier = 'High' THEN 1 ELSE 0 END) AS high_risk
                FROM {CATALOG}.{GOLD}.churn_scores
                GROUP BY region ORDER BY high_risk DESC LIMIT 5
            """)
            region_text = ", ".join(f"{r['region']}: {int(r['high_risk'])} at-risk" for r in regional)
            context_parts.append(f"Churn by region: {region_text}.")

        # Demand context
        if any(word in q for word in ["demand", "forecast", "trending", "sales", "category"]):
            demand = query(f"""
                SELECT sku_name, category, trend, demand_7d_avg
                FROM {CATALOG}.{GOLD}.demand_forecast
                WHERE trend = 'UP'
                ORDER BY demand_7d_avg DESC LIMIT 5
            """)
            items = ", ".join(f"{r['sku_name']} ({r['category']})" for r in demand)
            context_parts.append(f"Top trending SKUs (demand UP): {items}.")

        # Staffing context
        if any(word in q for word in ["staff", "headcount", "labor", "understaffed", "employee"]):
            staff = query(f"""
                SELECT COUNT(*) AS gaps
                FROM {CATALOG}.{PIPELINE}.store_staffing_summary
                WHERE staffing_status = 'UNDERSTAFFED'
            """)
            context_parts.append(f"Staffing: {int(staff[0]['gaps'])} role/store combinations are understaffed.")

    except Exception as e:
        context_parts.append(f"[Data retrieval partial — continuing with available context]")

    context_text = " ".join(context_parts) if context_parts else "No specific data available for this query."

    # Call Databricks Foundation Model API via raw HTTP (sdk typed helper has version issues)
    n_customers = int(kpis[0]['total_customers']) if kpis else 1000
    system_msg = (
        f"You are RetailAdvisor, an AI assistant for retail executives at a {n_customers}-customer retail chain. "
        "Answer using ONLY the data provided. Be concise — 2-3 sentences max — and give a concrete recommendation."
    )
    payload = {
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": f"LIVE RETAIL DATA:\n{context_text}\n\nQUESTION: {req.query}"},
        ],
        "max_tokens": 250,
        "temperature": 0.1,
    }
    answer = None
    for model in ["databricks-meta-llama-3-3-70b-instruct", "databricks-dbrx-instruct"]:
        try:
            resp = get_client().api_client.do("POST", f"/serving-endpoints/{model}/invocations", body=payload)
            answer = resp["choices"][0]["message"]["content"]
            break
        except Exception:
            continue
    if answer is None:
        bullets = "\n".join(f"• {p}" for p in context_parts)
        answer = f"Here's what the live data shows:\n\n{bullets}"

    return {"answer": answer, "context_used": len(context_parts)}


# ════════════════════════════════════════════════════════════════════════════════
# SERVE REACT SPA
# Mount /assets BEFORE the catch-all route
# ════════════════════════════════════════════════════════════════════════════════
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    from fastapi.responses import HTMLResponse
    with open("static/index.html", "r") as f:
        html = f.read()
    # Inject runtime config before </head> so React can read window.__GENIE_SPACE_ID__
    injection = f'<script>window.__GENIE_SPACE_ID__="{GENIE_SPACE_ID}";</script>'
    html = html.replace("</head>", injection + "</head>", 1)
    return HTMLResponse(html)
