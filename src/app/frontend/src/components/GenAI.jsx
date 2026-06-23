import { useState, useRef, useEffect } from 'react'

const DB_RED = '#FF3621'

const SUGGESTED = [
  "Which customers are at highest churn risk this month?",
  "How many inventory items need immediate reorder?",
  "Which region has the most at-risk customers?",
  "What are the top trending SKUs in demand?",
  "Are any stores understaffed right now?",
  "How much revenue is at risk from churning customers?",
]

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16,
    }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: '50%', background: DB_RED,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 14, fontWeight: 700, flexShrink: 0, marginRight: 10,
        }}>R</div>
      )}
      <div style={{
        maxWidth: '70%',
        background: isUser ? DB_RED : '#fff',
        color: isUser ? '#fff' : '#1a1a1a',
        padding: '12px 16px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        fontSize: 14,
        lineHeight: 1.6,
        boxShadow: isUser ? 'none' : '0 1px 4px rgba(0,0,0,0.08)',
      }}>
        {msg.content}
      </div>
    </div>
  )
}

export default function GenAI() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I'm RetailAdvisor, powered by Databricks. I have live access to your customer data, churn scores, inventory signals, and demand forecasts. What would you like to know?",
    }
  ])
  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text) {
    const q = (text || input).trim()
    if (!q) return

    setMessages(prev => [...prev, { role: 'user', content: q }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error connecting to RetailAdvisor. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', flexDirection: 'column' }}>

      {/* Header bar */}
      <div style={{ padding: '16px 48px', background: '#fff', borderBottom: '1px solid #e0e0e0', flexShrink: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 15, color: '#1a1a1a' }}>RetailAdvisor AI</div>
        <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
          Grounded in live data · Customer 360 · Churn scores · Inventory signals · Demand forecast
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Chat area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px 48px' }}>
            {messages.map((m, i) => <Message key={i} msg={m} />)}
            {loading && (
              <div style={{ display: 'flex', marginBottom: 16 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', background: DB_RED,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 14, fontWeight: 700, marginRight: 10, flexShrink: 0,
                }}>R</div>
                <div style={{ background: '#fff', borderRadius: '16px 16px 16px 4px', padding: '12px 16px', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', color: '#888', fontSize: 13 }}>
                  Querying Databricks...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{ padding: '16px 48px', background: '#fff', borderTop: '1px solid #e0e0e0', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Ask about customers, churn, inventory, demand, or staffing..."
                style={{
                  flex: 1, padding: '12px 16px', borderRadius: 8, fontSize: 14,
                  border: '1.5px solid #e0e0e0', outline: 'none',
                  fontFamily: 'inherit',
                }}
              />
              <button
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                style={{
                  background: loading || !input.trim() ? '#ccc' : DB_RED,
                  color: '#fff', border: 'none', borderRadius: 8,
                  padding: '12px 24px', cursor: loading || !input.trim() ? 'default' : 'pointer',
                  fontSize: 14, fontWeight: 700,
                }}
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Suggested questions sidebar */}
        <div style={{ width: 280, borderLeft: '1px solid #e0e0e0', padding: 24, background: '#fafafa', flexShrink: 0, overflowY: 'auto' }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: '#555' }}>Suggested Questions</div>
          {SUGGESTED.map((q, i) => (
            <button key={i} onClick={() => sendMessage(q)} style={{
              display: 'block', width: '100%', textAlign: 'left', marginBottom: 10,
              background: '#fff', border: '1px solid #e0e0e0', borderRadius: 6,
              padding: '10px 12px', cursor: 'pointer', fontSize: 12, color: '#333',
              lineHeight: 1.5, transition: 'border-color 0.15s',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = DB_RED}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#e0e0e0'}
            >
              {q}
            </button>
          ))}
        </div>

      </div>
    </div>
  )
}
