import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const DB_RED = '#FF3621'
const TIER_COLOR = { High: '#e74c3c', Medium: '#f39c12', Low: '#27ae60' }

export default function ChurnRisk({ churn, regional, segments, error }) {
  const [contacted, setContacted] = useState({})

  if (error)  return <div style={{ padding: 40, color: '#e74c3c' }}>Error: {error}</div>
  if (!churn) return <div style={{ padding: 40, color: '#888' }}>Loading churn data from Databricks...</div>

  function handleContact(row) {
    const key = row.customer_id
    setContacted(prev => ({ ...prev, [key]: 'sent' }))
  }

  return (
    <div style={{ padding: '32px 48px' }}>

      {/* Charts Row */}
      <div style={{ display: 'flex', gap: 24, marginBottom: 32 }}>

        {/* Regional stacked bar */}
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Churn Risk by Region</div>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>Stacked count — High / Medium / Low</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={regional || []} margin={{ left: 10 }}>
              <XAxis dataKey="region" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="High"   stackId="a" fill="#e74c3c" />
              <Bar dataKey="Medium" stackId="a" fill="#f39c12" />
              <Bar dataKey="Low"    stackId="a" fill="#27ae60" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Segment bar */}
        <div style={{ flex: 1, background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>High-Risk Rate by Segment</div>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>% of segment at high churn risk</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={segments || []} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={v => `${v}%`} />
              <YAxis type="category" dataKey="segment" width={80} tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`${v}%`, 'High-risk rate']} />
              <Bar dataKey="high_risk_pct" fill={DB_RED} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>

      {/* At-risk customer table */}
      <div style={{ background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Top At-Risk Customers — Highest Probability First</div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>High churn risk · sorted by churn probability · last 90 days of activity</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f5f5f5' }}>
              {['Customer', 'Region', 'Segment', 'Recency (days)', 'Orders 90d', 'Spend 90d', 'Churn Prob', ''].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#555', fontSize: 12 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {churn.map((row, i) => {
              const key   = row.customer_id
              const state = contacted[key]
              const prob  = parseFloat(row.churn_prob)
              return (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                  <td style={{ padding: '9px 12px', fontFamily: 'monospace', fontSize: 12 }}>{row.customer_name}</td>
                  <td style={{ padding: '9px 12px' }}>{row.region}</td>
                  <td style={{ padding: '9px 12px' }}>{row.segment}</td>
                  <td style={{ padding: '9px 12px' }}>
                    <span style={{
                      background: parseInt(row.recency_days) > 60 ? '#fdecea' : '#fff8e1',
                      color:      parseInt(row.recency_days) > 60 ? '#c0392b' : '#e67e22',
                      padding: '2px 8px', borderRadius: 4, fontWeight: 700, fontSize: 12,
                    }}>
                      {row.recency_days}d
                    </span>
                  </td>
                  <td style={{ padding: '9px 12px' }}>{row.order_count_90d}</td>
                  <td style={{ padding: '9px 12px' }}>${parseFloat(row.total_spend_90d || 0).toFixed(0)}</td>
                  <td style={{ padding: '9px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{
                        width: 60, height: 6, background: '#eee', borderRadius: 3, overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${prob * 100}%`, height: '100%',
                          background: prob > 0.7 ? '#e74c3c' : prob > 0.5 ? '#f39c12' : '#27ae60',
                          borderRadius: 3,
                        }} />
                      </div>
                      <span style={{ fontWeight: 700, color: prob > 0.7 ? '#e74c3c' : '#1a1a1a' }}>
                        {(prob * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '9px 12px' }}>
                    {state === 'sent' ? (
                      <span style={{ color: '#27ae60', fontWeight: 600, fontSize: 12 }}>✓ Contacted</span>
                    ) : (
                      <button
                        onClick={() => handleContact(row)}
                        style={{
                          background: DB_RED, color: '#fff', border: 'none', borderRadius: 4,
                          padding: '5px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 700,
                        }}
                      >
                        Reach Out
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

    </div>
  )
}
