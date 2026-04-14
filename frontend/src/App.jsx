import { useEffect, useMemo, useRef, useState } from 'react'

function App() {
  const [role, setRole] = useState('patient')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      sender: 'assistant',
      text: 'Hello! Ask me about doctor availability or booking an appointment.',
    },
  ])

  const messagesEndRef = useRef(null)

  const roleLabel = useMemo(
    () => (role === 'patient' ? 'Login as Patient' : 'Login as Doctor'),
    [role],
  )

  const submitPrompt = async (promptText, displayText) => {
    const nextPrompt = promptText.trim()
    if (!nextPrompt || loading) {
      return
    }

    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        sender: 'user',
        text: displayText ?? promptText,
      },
    ])

    setPrompt('')
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: nextPrompt, role }),
      })

      if (!response.ok) {
        throw new Error('Backend returned an error')
      }

      const data = await response.json()
      const assistantText =
        typeof data?.response === 'string' && data.response.trim()
          ? data.response
          : 'I could not parse the backend response.'

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: assistantText,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: 'I was unable to reach the backend. Please try again.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async (event) => {
    event.preventDefault()
    await submitPrompt(prompt)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <div className="mx-auto flex h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70 shadow-2xl shadow-slate-950/50 backdrop-blur">
        <header className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-cyan-300/80">
              Doctor Assistant
            </p>
            <h1 className="text-lg font-semibold text-slate-100">
              Appointment Chat
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-slate-400 sm:inline">Role</span>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-400 transition focus:ring-2"
            >
              <option value="patient">Login as Patient</option>
              <option value="doctor">Login as Doctor</option>
            </select>
          </div>
        </header>

        {role === 'doctor' && (
          <div className="border-b border-slate-800 px-5 py-3">
            <button
              type="button"
              onClick={() =>
                submitPrompt('Get my daily stats and summarize them', 'Generate Daily Report')
              }
              disabled={loading}
              className="rounded-xl border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Generate Daily Report
            </button>
          </div>
        )}

        <section className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[75%] ${
                    message.sender === 'user'
                      ? 'rounded-br-sm bg-cyan-500 text-slate-950'
                      : 'rounded-bl-sm border border-slate-700 bg-slate-800 text-slate-100'
                  }`}
                >
                  <p className="mb-1 text-[10px] uppercase tracking-[0.18em] opacity-70">
                    {message.sender === 'user' ? roleLabel : 'Assistant'}
                  </p>
                  <p>{message.text}</p>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-200">
                  <p className="mb-1 text-[10px] uppercase tracking-[0.18em] opacity-70">
                    Assistant
                  </p>
                  <p className="animate-pulse">Thinking...</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </section>

        <form
          onSubmit={sendMessage}
          className="border-t border-slate-800 bg-slate-900 px-4 py-4 sm:px-6"
        >
          <div className="flex items-end gap-3">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Type your message..."
              rows={2}
              className="max-h-36 min-h-[52px] flex-1 resize-y rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none ring-cyan-400 placeholder:text-slate-500 focus:ring-2"
            />
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="rounded-xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </main>
  )
}

export default App
