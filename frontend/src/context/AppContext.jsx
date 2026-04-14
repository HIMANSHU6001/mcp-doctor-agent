/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const AppContext = createContext(null)

function initialUser() {
  try {
    const stored = window.localStorage.getItem('doctor-assistant-user')
    return stored ? JSON.parse(stored) : null
  } catch {
    return null
  }
}

function initialSessionId() {
  return window.localStorage.getItem('doctor-assistant-session-id') ?? crypto.randomUUID()
}

export function AppProvider({ children }) {
  const [role, setRole] = useState('patient')
  const [user, setUserState] = useState(initialUser)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(initialSessionId)

  const setUser = (profile) => {
    setUserState(profile)
    if (profile) {
      window.localStorage.setItem('doctor-assistant-user', JSON.stringify(profile))
    } else {
      window.localStorage.removeItem('doctor-assistant-user')
    }
  }

  const setSession = (nextSessionId) => {
    setSessionId(nextSessionId)
    window.localStorage.setItem('doctor-assistant-session-id', nextSessionId)
  }

  const sendMessage = async (text) => {
    if (!text || isLoading) {
      return
    }

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
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
        setSession(data.session_id)
      }

      setMessages((prev) => [...prev, { role: 'assistant', content: assistantText }])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'I was unable to reach the backend. Please try again.',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    setUser(null)
    setMessages([])
    const freshSessionId = crypto.randomUUID()
    setSession(freshSessionId)
  }

  const value = {
    role,
    setRole,
    user,
    setUser,
    messages,
    isLoading,
    sendMessage,
    logout,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used inside AppProvider')
  }
  return context
}
