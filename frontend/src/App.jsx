import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function App() {
  const [status, setStatus] = useState('checking…')

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main>
      <h1>Agent HQ</h1>
      <p>Chat with AI agents, each with its own role. Coming soon.</p>
      <p className="status">
        Backend: <code>{status}</code>
      </p>
    </main>
  )
}

export default App
