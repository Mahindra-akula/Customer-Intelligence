const DB_RED = '#FF3621'

const Box = ({ label, color, detail, badge }) => (
  <div style={{ background: color, borderRadius: 8, padding: '14px 18px', minWidth: 150, textAlign: 'center', color: '#fff', flexShrink: 0, position: 'relative' }}>
    {badge && (
      <div style={{
        position: 'absolute', top: -8, right: -8,
        background: DB_RED, color: '#fff', borderRadius: 10,
        fontSize: 9, fontWeight: 700, padding: '2px 6px', letterSpacing: 0.5
      }}>{badge}</div>
    )}
    <div style={{ fontWeight: 700, fontSize: 12 }}>{label}</div>
    <div style={{ fontSize: 10, opacity: 0.85, marginTop: 6, lineHeight: 1.5, whiteSpace: 'pre-line' }}>{detail}</div>
  </div>
)

const Arrow = ({ vertical }) => (
  <div style={{
    fontSize: 20, color: '#bbb', flexShrink: 0,
    ...(vertical
      ? { textAlign: 'center', margin: '10px 0' }
      : { alignSelf: 'center', padding: '0 6px' })
  }}>
    {vertical ? '↓' : '→'}
  </div>
)

const LayerLabel = ({ text }) => (
  <div style={{ fontSize: 10, fontWeight: 700, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 }}>{text}</div>
)

export default function Architecture({ platform }) {
  const totalRows = platform?.tables?.reduce((s, t) => s + t.rows, 0) || 0

  return (
    <div style={{ padding: '32px 64px', overflowY: 'auto' }}>
      <h2 style={{ color: '#1a1a1a', marginBottom: 4, fontSize: 22 }}>Solution Architecture</h2>
      <p style={{ color: '#777', marginBottom: 36, fontSize: 13 }}>
        Retail Customer Intelligence · Databricks Free Edition · 4 Layers · {totalRows.toLocaleString()} records processed
      </p>

      {/* ── Layer 1: Sources ──────────────────────────────────────────────── */}
      <LayerLabel text="Layer 1 — Governed Data Foundation" />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        <Box label="Postgres" color="#3d3d3d" detail={'Customers\nOrders'} badge="Source 1" />
        <Arrow />
        <Box label="MySQL" color="#3d3d3d" detail={'Products\nInventory'} badge="Source 2" />
        <Arrow />
        <Box label="Salesforce CSV" color="#3d3d3d" detail={'CRM Events\nSupport Tickets'} badge="SaaS" />
        <Arrow />
        <Box label="HR Export" color="#3d3d3d" detail={'Staffing\nHeadcount'} badge="SaaS" />
      </div>
      <Arrow vertical />

      {/* ── Medallion ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        <Box label="Bronze" color="#c0392b" detail={'Raw ingestion\nDelta Live Tables\nLineage tracked'} />
        <Arrow />
        <Box label="Silver" color="#d35400" detail={'DLT quality checks\nTyped + deduped\nCRM summary'} />
        <Arrow />
        <Box label="Gold · Customer 360" color="#27ae60" detail={'CORE ENTITY\nUnified profile\nChurn features'} badge="Single Truth" />
      </div>
      <Arrow vertical />

      {/* ── Layer 2: ML ───────────────────────────────────────────────────── */}
      <LayerLabel text="Layer 2 — Predictive ML" />
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <Box label="Churn Model" color="#8e44ad" detail={'XGBoost · MLflow\ngold.churn_scores\nHigh / Med / Low'} badge="Primary" />
        <Box label="Demand Forecast" color="#8e44ad" detail={'Rolling 7d avg\ngold.demand_forecast\nUP / DOWN / FLAT'} />
        <Box label="Inventory Health" color="#8e44ad" detail={'Days of supply\nREORDER / WATCH / OK\nAuto-signal'} />
      </div>
      <Arrow vertical />

      {/* ── Layer 3: GenAI ────────────────────────────────────────────────── */}
      <LayerLabel text="Layer 3 — GenAI Activation" />
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <Box label="Vector Search" color="#1a6b9e" detail={'CRM notes indexed\nDatabricks GTE embeds\nSemantic retrieval'} />
        <Box label="RAG Chain" color="#1a6b9e" detail={'SQL context + docs\nDatabricks DBRX\ngold.rag_documents'} />
        <Box label="RetailAdvisor" color="#1a6b9e" detail={'Natural language Q&A\nLive data grounded\nNo hallucination'} badge="GenAI" />
      </div>
      <Arrow vertical />

      {/* ── Layer 4: Presentation ─────────────────────────────────────────── */}
      <LayerLabel text="Layer 4 — Business Presentation" />
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Box label="Executive Overview" color="#2471a3" detail={'KPI scorecards\nRevenue at risk\nChurn distribution'} />
        <Box label="Churn Risk Center" color="#2471a3" detail={'At-risk customers\nRegional heatmap\nSegment breakdown'} />
        <Box label="RetailAdvisor AI" color="#2471a3" detail={'Chat interface\nSuggested questions\nInstant answers'} />
        <Box label="This App" color={DB_RED} detail={'One URL\nAll personas\nZero connectors'} />
      </div>

      {/* ── Platform rules ────────────────────────────────────────────────── */}
      <div style={{
        marginTop: 36, borderTop: '1px solid #eee', paddingTop: 18,
        display: 'flex', justifyContent: 'center', gap: 32, flexWrap: 'wrap',
        color: '#aaa', fontSize: 11,
      }}>
        {[
          'Serverless compute only',
          'Unity Catalog · 3-part table refs',
          'Delta Lake · open format',
          'MLflow Model Registry',
          'Databricks App · one-command deploy',
        ].map(t => <span key={t}>{t}</span>)}
      </div>

    </div>
  )
}
