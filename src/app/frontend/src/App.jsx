import { useState, useEffect } from 'react'
import Executive    from './components/Executive'
import ChurnRisk    from './components/ChurnRisk'
import GenAI        from './components/GenAI'
import Architecture from './components/Architecture'

const TABS = [
  { key: 'executive',    label: 'Executive Overview',    sub: 'Business Leader — churn rate, revenue at risk, KPIs' },
  { key: 'churn',        label: 'Churn Risk Center',     sub: 'VP of Engineering — at-risk customers, regional breakdown' },
  { key: 'genai',        label: 'RetailAdvisor AI',      sub: 'GenAI — natural language over customer data' },
  { key: 'architecture', label: 'Solution Architecture', sub: 'CTO — 4-layer data + ML + GenAI platform view' },
]

const DB_RED = '#FF3621'

export default function App() {
  const [active, setActive] = useState('executive')

  // Data lifted here — fetched ONCE at mount, passed as props to all tabs
  // Eliminates reload delay on every tab switch
  const [summary,   setSummary]   = useState(null)
  const [churn,     setChurn]     = useState(null)
  const [regional,  setRegional]  = useState(null)
  const [segments,  setSegments]  = useState(null)
  const [platform,  setPlatform]  = useState(null)
  const [errors,    setErrors]    = useState({})

  useEffect(() => {
    const load = (url, setter, key) =>
      fetch(url)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
        .then(setter)
        .catch(e => setErrors(prev => ({ ...prev, [key]: e.message })))

    load('/api/summary',         setSummary,  'summary')
    load('/api/churn-scores',    setChurn,    'churn')
    load('/api/regional-churn',  setRegional, 'regional')
    load('/api/churn-by-segment',setSegments, 'segments')
    load('/api/platform-stats',  setPlatform, 'platform')
  }, [])

  const current = TABS.find(t => t.key === active)

  return (
    <div style={{ fontFamily: "'Segoe UI', system-ui, sans-serif", height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ height: 64, padding: '0 32px', display: 'flex', alignItems: 'center', borderBottom: '1px solid #e0e0e0', background: '#fff', flexShrink: 0 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: DB_RED }}>Retail Customer Intelligence</div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>Customer 360 · Churn ML · GenAI · Powered by Databricks</div>
        </div>
      </div>

      {/* Nav */}
      <div style={{ height: 52, padding: '0 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fafafa', borderBottom: '1px solid #e0e0e0', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {TABS.map(t => (
            <button key={t.key} onClick={() => setActive(t.key)} style={{
              padding: '7px 18px', cursor: 'pointer', borderRadius: 4, fontSize: 13, fontWeight: 600,
              border: `1.5px solid ${DB_RED}`,
              background: active === t.key ? DB_RED : '#fff',
              color:      active === t.key ? '#fff' : DB_RED,
              transition: 'all 0.15s',
            }}>
              {t.label}
            </button>
          ))}
        </div>
        <div style={{ color: '#999', fontSize: 12, fontStyle: 'italic' }}>{current?.sub}</div>
      </div>

      {/* Content — all tabs mounted, only active one visible (display:none keeps iframe + state alive) */}
      <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
        <div style={{ display: active === 'executive'    ? 'block' : 'none', height: '100%' }}>
          <Executive summary={summary} error={errors.summary} />
        </div>
        <div style={{ display: active === 'churn'        ? 'block' : 'none', height: '100%' }}>
          <ChurnRisk churn={churn} regional={regional} segments={segments} error={errors.churn || errors.regional} />
        </div>
        <div style={{ display: active === 'genai'        ? 'block' : 'none', height: '100%' }}>
          <GenAI />
        </div>
        <div style={{ display: active === 'architecture' ? 'block' : 'none', height: '100%' }}>
          <Architecture platform={platform} />
        </div>
      </div>

    </div>
  )
}
