import { GoogleLogin } from '@react-oauth/google'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge } from './components/ui/badge'
import { Button } from './components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Select } from './components/ui/select'
import { Textarea } from './components/ui/textarea'

function App() {
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const [role, setRole] = useState('patient')
  const [prompt, setPrompt] = useState('')
  const [sessionId, setSessionId] = useState(
    () => window.localStorage.getItem('doctor-assistant-session-id') ?? crypto.randomUUID(),
  )
  const [user, setUser] = useState(() => {
    try {
      const storedUser = window.localStorage.getItem('doctor-assistant-user')
      return storedUser ? JSON.parse(storedUser) : null
    } catch {
      return null
    }
  })
  const [authLoading, setAuthLoading] = useState(false)
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

  const selectedRoleLabel = role === 'patient' ? 'Patient' : 'Doctor'

  const handleGoogleSuccess = async (credentialResponse) => {
    const token = credentialResponse?.credential
    if (!token) {
      return
    }

    setAuthLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/auth/google', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      })

      if (!response.ok) {
        throw new Error('Google sign-in failed')
      }

      const data = await response.json()
      const profile = {
        email: data.email,
        name: data.name,
        picture: data.picture ?? null,
      }

      setUser(profile)
      window.localStorage.setItem('doctor-assistant-user', JSON.stringify(profile))
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: 'Google sign-in failed. Please try again.',
        },
      ])
    } finally {
      setAuthLoading(false)
    }
  }

  const handleSignOut = () => {
    setUser(null)
    window.localStorage.removeItem('doctor-assistant-user')
  }

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
        body: JSON.stringify({
          prompt: nextPrompt,
          role,
          session_id: sessionId,
          user_name: user?.name ?? null,
          user_email: user?.email ?? null,
        }),
      })

      if (!response.ok) {
        throw new Error('Backend returned an error')
      }

      const data = await response.json()
      const assistantText =
        typeof data?.response === 'string' && data.response.trim()
          ? data.response
          : 'I could not parse the backend response.'

      if (typeof data?.session_id === 'string' && data.session_id.trim()) {
        setSessionId(data.session_id)
      }

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

  useEffect(() => {
    window.localStorage.setItem('doctor-assistant-session-id', sessionId)
  }, [sessionId])

  useEffect(() => {
    if (user) {
      window.localStorage.setItem('doctor-assistant-user', JSON.stringify(user))
    }
  }, [user])

  if (!user) {
    return (
      <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900">
        <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-3xl items-center justify-center">
          <Card className="w-full overflow-hidden rounded-3xl border-slate-200 shadow-xl">
            <CardHeader className="border-b border-slate-200 bg-slate-100/60">
              <Badge variant="secondary" className="w-fit">Doctor Assistant</Badge>
              <CardTitle>Sign in to continue</CardTitle>
              <CardDescription>
                Choose your role, then authenticate with Google before chatting.
              </CardDescription>
            </CardHeader>

            <CardContent className="grid gap-6 py-6 md:grid-cols-2">
              <div className="space-y-4">
                <Button
                  type="button"
                  variant={role === 'patient' ? 'default' : 'outline'}
                  size="lg"
                  onClick={() => setRole('patient')}
                  className="h-auto w-full flex-col items-start gap-1 rounded-2xl px-4 py-4 text-left"
                >
                  <div className="text-sm font-semibold">Login as Patient</div>
                  <div className="text-xs text-slate-500">
                    Book appointments and ask about availability.
                  </div>
                </Button>

                <Button
                  type="button"
                  variant={role === 'doctor' ? 'default' : 'outline'}
                  size="lg"
                  onClick={() => setRole('doctor')}
                  className="h-auto w-full flex-col items-start gap-1 rounded-2xl px-4 py-4 text-left"
                >
                  <div className="text-sm font-semibold">Login as Doctor</div>
                  <div className="text-xs text-slate-500">
                    Review daily stats and manage appointments.
                  </div>
                </Button>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Selected Role</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{selectedRoleLabel}</p>
                <p className="mt-1 text-sm text-slate-500">
                  Sign in with the Google account you want to use for this session.
                </p>

                <div className="mt-5">
                  {authLoading ? (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      Signing in...
                    </div>
                  ) : googleClientId ? (
                    <GoogleLogin
                      onSuccess={handleGoogleSuccess}
                      onError={() => {
                        setMessages((prev) => [
                          ...prev,
                          {
                            id: crypto.randomUUID(),
                            sender: 'assistant',
                            text: 'Google sign-in failed to initialize.',
                          },
                        ])
                      }}
                      text="signin_with"
                      shape="rectangular"
                      theme="filled_blue"
                      size="large"
                    />
                  ) : (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                      Set VITE_GOOGLE_CLIENT_ID to enable Google sign-in.
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900">
      <Card className="mx-auto flex h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border-slate-200 shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-200 bg-slate-100/70 px-5 py-4">
          <div>
            <Badge variant="secondary">Doctor Assistant</Badge>
            <h1 className="mt-2 text-lg font-semibold text-slate-900">
              Appointment Chat
            </h1>
            {user && (
              <p className="mt-1 text-sm text-slate-500">
                Signed in as {user.name} ({user.email})
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-3 sm:flex-row sm:items-center">
            <span className="hidden text-xs text-slate-500 sm:inline">Role</span>
            <Select
              value={role}
              onChange={(event) => setRole(event.target.value)}
              className="w-auto min-w-44"
            >
              <option value="patient">Login as Patient</option>
              <option value="doctor">Login as Doctor</option>
            </Select>
            {user ? (
              <Button
                type="button"
                onClick={handleSignOut}
                variant="outline"
              >
                Sign out
              </Button>
            ) : null}
          </div>
        </header>

        {role === 'doctor' && (
          <div className="border-b border-slate-200 bg-slate-50 px-5 py-3">
            <Button
              type="button"
              onClick={() =>
                submitPrompt('Get my daily stats and summarize them', 'Generate Daily Report')
              }
              disabled={loading}
              variant="secondary"
              className="rounded-xl"
            >
              Generate Daily Report
            </Button>
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
                      ? 'rounded-br-sm bg-slate-900 text-white'
                      : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800'
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
                <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
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
          className="border-t border-slate-200 bg-slate-100/70 px-4 py-4 sm:px-6"
        >
          <div className="flex items-end gap-3">
            <Textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Type your message..."
              rows={2}
              className="max-h-36 min-h-[52px] flex-1 resize-y rounded-xl border-slate-300 bg-white"
            />
            <Button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="rounded-xl"
            >
              {loading ? 'Sending...' : 'Send'}
            </Button>
          </div>
        </form>
      </Card>
    </main>
  )
}

export default App
