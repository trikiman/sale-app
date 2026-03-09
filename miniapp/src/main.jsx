import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Global error logger — helps debug Safari/mobile crashes
window.addEventListener('error', (e) => {
  const msg = `[JS ERROR] ${e.message} @ ${e.filename}:${e.lineno}`
  console.error(msg)
  try { fetch('/api/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ level: 'error', msg, ua: navigator.userAgent }) }) } catch {}
})
window.addEventListener('unhandledrejection', (e) => {
  const msg = `[UNHANDLED] ${e.reason}`
  console.error(msg)
  try { fetch('/api/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ level: 'error', msg, ua: navigator.userAgent }) }) } catch {}
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
