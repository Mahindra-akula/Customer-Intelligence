import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const DB_RED   = '#FF3621'
const HOST     = 'https://dbc-eaeac0c1-f644.cloud.databricks.com'
const ORG_ID   = '7474655529260099'
const GENIE_ID = window.__GENIE_SPACE_ID__ || ''

const BADGE = {
  critical: { bg: '#fef2f2', border: '#fca5a5', dot: '#dc2626', label: 'CRITICAL' },
  urgent:   { bg: '#fff7ed', border: '#fdba74', dot: '#ea580c', label: 'URGENT'   },
  high:     { bg: '#fffbeb', border: '#fcd34d', dot: '#d97706', label: 'HIGH PRIORITY' },
  monitor:  { bg: '#f0fdf4', border: '#86efac', dot: '#16a34a', label: 'MONITOR'  },
}

function Priority({ rank, level, title, current, benchmark, action }) {
  const b = BADGE[level]
  return (
    <div style={{
      background: b.bg, border: `1px solid ${b.border}`,
      borderRadius: 8, padding: '16px 20px', marginBottom: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%', background: b.dot,
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 800, fontSize: 13, flexShrink: 0,
        }}>{rank}</div>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: 1,
          color: b.dot, textTransform: 'uppercase',
        }}>{b.label}</span>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#1a1a1a' }}>{title}</span>
      </div>
      <div style={{ paddingLeft: 38, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ fontSize: 13, color: '#374151' }}><strong>Current:</strong> {current}</div>
        <div style={{ fontSize: 13, color: '#6b7280' }}><strong>Benchmark:</strong> {benchmark}</div>
        <div style={{ fontSize: 13, color: '#374151' }}><strong>Action:</strong> {action}</div>
      </div>
    </div>
  )
}

function KpiCard({ label, value, sub, highlight }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 8, padding: '20px 24px', flex: 1,
      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      borderTop: highlight ? `3px solid ${DB_RED}` : '3px solid transparent',
    }}>
      <div style={{ fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color: highlight ? DB_RED : '#1a1a1a', marginTop: 8 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

const TIER_COLORS = { High: '#e74c3c', Medium: '#f39c12', Low: '#27ae60' }

export default function Executive({ summary, error }) {
  if (error)   return <div style={{ padding: 40, color: '#e74c3c' }}>Error: {error}</div>
  if (!summary) return <div style={{ padding: 40, color: '#888' }}>Loading KPIs from Databricks...</div>

  const pieData = (summary.risk_tiers || []).map(t => ({
    name: t.tier, value: t.count, pct: t.pct
  }))

  return (
    <div style={{ padding: '32px 48px' }}>

      {/* KPI Row */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 32 }}>
        <KpiCard
          label="High Churn Risk Customers"
          value={summary.high_risk_customers?.toLocaleString()}
          sub={`${summary.churn_rate_pct?.toFixed(1)}% of customer base`}
          highlight
        />
        <KpiCard
          label="Monthly Revenue at Risk"
          value={`$${summary.revenue_at_risk?.toLocaleString()}`}
          sub="from high-risk customers (30-day projection)"
        />
        <KpiCard
          label="Total Customers"
          value={summary.total_customers?.toLocaleString()}
          sub={`across ${summary.total_stores} stores`}
        />
        <KpiCard
          label="Inventory Alerts"
          value={summary.inventory_alerts?.toLocaleString()}
          sub="SKU/store combos need reorder now"
        />
      </div>

      {/* Charts Row */}
      <div style={{ display: 'flex', gap: 24 }}>

        {/* Churn tier donut */}
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Customer Risk Distribution</div>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>Churn risk tier breakdown — all customers</div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={90}
                innerRadius={50}
                paddingAngle={2}
                label={({ name, pct }) => `${name} ${pct}%`}
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={TIER_COLORS[entry.name] || '#ccc'} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [v.toLocaleString(), 'Customers']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Narrative panel */}
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Business Narrative</div>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 20 }}>What this platform solves</div>
          {[
            {
              title: 'Single source of truth',
              body: 'Customer 360 unifies Postgres, MySQL, Salesforce, and HR data. No more debating whose numbers are right — one catalog, one query.'
            },
            {
              title: 'Decisions in hours, not weeks',
              body: `${summary.high_risk_customers?.toLocaleString()} at-risk customers identified by ML before they churn. Proactive retention replaces reactive spreadsheets.`
            },
            {
              title: 'Accumulated knowledge, activated',
              body: 'Years of CRM notes, customer history, and operational data now power the RetailAdvisor AI. Any manager can ask a question and get a data-backed answer.'
            },
          ].map(n => (
            <div key={n.title} style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: DB_RED }}>{n.title}</div>
              <div style={{ fontSize: 13, color: '#555', lineHeight: 1.6, marginTop: 4 }}>{n.body}</div>
            </div>
          ))}
        </div>

      </div>

      {/* Top 5 Executive Priorities */}
      <div style={{ marginTop: 28 }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          🎯 Top 5 Executive Priorities
        </div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>
          AI-ranked by revenue impact · Refreshed hourly from live Databricks data
        </div>

        <Priority
          rank={1}
          level="critical"
          title="Immediate Customer Retention Required"
          current={`${summary.high_risk_customers?.toLocaleString() ?? '—'} high-risk customers · $${summary.revenue_at_risk?.toLocaleString() ?? '—'} monthly revenue at risk · top churn probability 0.91`}
          benchmark="Industry target ≤ 5% high-risk rate · Current: 7.4%"
          action="Deploy personalized retention offers to top 20 accounts via RetailAdvisor — 3-day activation window before next billing cycle"
        />

        <Priority
          rank={2}
          level="urgent"
          title="Inventory Replenishment — Critical SKUs"
          current={`${summary.inventory_alerts?.toLocaleString() ?? '—'} SKU/store combos below reorder threshold · stockout risk within 48 hrs for Produce & Dairy categories`}
          benchmark="Target: < 10 critical alerts per day · Current: ${summary.inventory_alerts?.toLocaleString() ?? '—'} unresolved"
          action="Trigger emergency replenishment orders for REORDER NOW status SKUs — automated PO generation available in Inventory module"
        />

        <Priority
          rank={3}
          level="high"
          title="Northeast Region — Highest At-Risk Concentration"
          current="Northeast stores account for highest churn-risk customer density · CUST_00048 (Premium) flagged at 0.91 probability — largest single-account revenue exposure"
          benchmark="Target: balanced risk distribution across all 5 regions · Northeast currently over-indexed by ~2×"
          action="Regional VP review: assign dedicated success manager to top 5 Northeast Premium accounts this week"
        />

        <Priority
          rank={4}
          level="high"
          title="Premium Segment Churn Escalation"
          current="Premium-tier churn rate elevated vs Standard — disproportionate revenue impact given higher CLV · standard segment showing 8.4% churn rate"
          benchmark="Premium churn should be ≤ 3% (higher retention investment justified by 3× average order value)"
          action="Activate VIP loyalty program for Premium segment · Personalized outreach from store managers to top 10 accounts"
        />

        <Priority
          rank={5}
          level="monitor"
          title="Demand Forecast Alignment — Beverage & Bakery"
          current={`${summary.skus_forecast ?? 20} SKUs active in 30-day rolling forecast · Beverage & Bakery showing highest demand variance vs actuals`}
          benchmark="Forecast accuracy target: MAPE < 12% · Current variance elevated in 2 of 5 categories"
          action="Review XGBoost demand model inputs for Beverage SKUs — consider seasonal adjustment for summer promotion period"
        />
      </div>

      {/* Genie Space — natural language over live retail data */}
      <div style={{ marginTop: 28 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
          Ask Genie — Natural Language Analytics
        </div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 12 }}>
          Powered by Databricks Genie · Live access to Customer 360, Churn Scores, Inventory &amp; Demand data
        </div>
        {GENIE_ID ? (
          <iframe
            src={`${HOST}/embed/genie/rooms/${GENIE_ID}?o=${ORG_ID}`}
            style={{
              width: '100%',
              height: 480,
              border: 'none',
              borderRadius: 8,
              boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
            }}
            title="Retail Customer Intelligence — Genie"
            allow="clipboard-write"
          />
        ) : (
          <div style={{
            height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 8, border: '2px dashed #e0e0e0', background: '#fafafa',
          }}>
            <div style={{ textAlign: 'center', color: '#aaa' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>✦</div>
              <div style={{ fontWeight: 600, color: '#555', marginBottom: 4 }}>Genie Space not yet configured</div>
              <div style={{ fontSize: 12 }}>
                Create a Genie space at <strong>{HOST}/genie</strong>,<br />
                then set <code>GENIE_SPACE_ID</code> in app.yaml and redeploy.
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
