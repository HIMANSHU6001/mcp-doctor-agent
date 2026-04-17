/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react'
import { toast } from 'sonner'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ROLE_STORAGE_KEY = 'doctor-assistant-role'
const VALID_ROLES = new Set(['patient', 'doctor'])

const AppContext = createContext(null)

function normalizeUserProfile(profile) {
  if (!profile) {
    return null
  }

  return {
    name: profile.name ?? '',
    email: profile.email ?? '',
    picture: profile.picture ?? null,
    slackConnected: Boolean(profile.slackConnected ?? profile.slack_connected),
  }
}

function initialUser() {
  try {
    const stored = window.localStorage.getItem('doctor-assistant-user')
    return stored ? normalizeUserProfile(JSON.parse(stored)) : null
  } catch {
    return null
  }
}

function initialSessionId() {
  try {
    const stored = window.localStorage.getItem('doctor-assistant-session-id')
    return stored || createSessionId()
  } catch {
    return createSessionId()
  }
}

function initialRole() {
  try {
    const storedRole = window.localStorage.getItem(ROLE_STORAGE_KEY)
    return VALID_ROLES.has(storedRole) ? storedRole : 'patient'
  } catch {
    return 'patient'
  }
}

function createSessionId() {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch {
    // Ignore and fall back to deterministic string generation.
  }

  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function AppProvider({ children }) {
  const [role, setRoleState] = useState(initialRole)
  const [user, setUserState] = useState(initialUser)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [reportStatus, setReportStatus] = useState(null)
  const [sessionId, setSessionId] = useState(initialSessionId)

  const postChatPrompt = async (text) => {
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

    return response.json()
  }

  const appendAssistantMessage = (data) => {
    const assistantText =
      typeof data?.response === 'string' && data.response.trim()
        ? data.response
        : 'I could not parse the backend response.'

    if (typeof data?.session_id === 'string' && data.session_id.trim()) {
      setSession(data.session_id)
    }

    setMessages((prev) => [...prev, { role: 'assistant', content: assistantText }])
    return assistantText
  }

  const setUser = (profile) => {
    const normalizedProfile = normalizeUserProfile(profile)
    setUserState(normalizedProfile)

    if (normalizedProfile) {
      window.localStorage.setItem('doctor-assistant-user', JSON.stringify(normalizedProfile))
    } else {
      window.localStorage.removeItem('doctor-assistant-user')
    }
  }

  const setSlackConnected = (connected) => {
    if (!user) {
      return
    }

    setUser({ ...user, slackConnected: Boolean(connected) })
  }

  const setSession = (nextSessionId) => {
    setSessionId(nextSessionId)
    window.localStorage.setItem('doctor-assistant-session-id', nextSessionId)
  }

  const setRole = (nextRole) => {
    const normalizedRole = VALID_ROLES.has(nextRole) ? nextRole : 'patient'
    setRoleState(normalizedRole)
    window.localStorage.setItem(ROLE_STORAGE_KEY, normalizedRole)
  }

  const sendMessage = async (text) => {
    if (!text || isLoading) {
      return
    }

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setIsLoading(true)

    try {
      const data = await postChatPrompt(text)
      appendAssistantMessage(data)
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

  const clearReportStatus = () => {
    setReportStatus(null)
  }

  const sendDoctorReportNotification = async (date = null) => {
    if (isLoading) {
      return { ok: false, message: 'A request is already in progress.' }
    }

    if (!user?.email) {
      const nextStatus = {
        state: 'error',
        message: 'Doctor email is required to send report notifications.',
      }
      setReportStatus(nextStatus)
      toast.error(nextStatus.message)
      return { ok: false, message: nextStatus.message }
    }

    setIsLoading(true)
    setReportStatus({ state: 'loading', message: 'Sending doctor report notification...' })

    const reportPrompt = date
      ? `Generate my daily report for ${date}. Send it to my email and also to Slack if connected.`
      : 'Generate my daily report for today. Send it to my email and also to Slack if connected.'

    try {
      setMessages((prev) => [...prev, { role: 'user', content: reportPrompt }])

      const data = await postChatPrompt(reportPrompt)
      const reportText = appendAssistantMessage(data)
      const toolOutcomes = Array.isArray(data?.tool_outcomes) ? data.tool_outcomes : []
      const reportOutcome = [...toolOutcomes].reverse().find(
        (entry) => entry?.tool === 'send_doctor_report_notification',
      )
      const result = reportOutcome?.result && typeof reportOutcome.result === 'object'
        ? reportOutcome.result
        : null
      const deliveryStatus = result?.delivery_status
      const emailDelivery = result?.delivery?.email ?? null
      const slackDelivery = result?.delivery?.slack ?? null

      let nextStatus = {
        state: 'error',
        message: result?.message || reportText || 'Unable to deliver report.',
      }

      if (deliveryStatus === 'all_success') {
        nextStatus = {
          state: 'success',
          message: 'Report sent to email and Slack.',
        }
        toast.success(nextStatus.message)
      } else if (deliveryStatus === 'partial_success') {
        const slackNotConnected = String(slackDelivery?.status || '') === 'not_connected'
        if (slackNotConnected && emailDelivery?.ok) {
          nextStatus = {
            state: 'warning',
            message: 'Report sent to email. Connect to Slack to get report on your Slack.',
          }
        } else {
          nextStatus = {
            state: 'warning',
            message: result?.message || 'Report delivered partially. Check channel status.',
          }
        }
        toast.warning(nextStatus.message)
      } else if (deliveryStatus === 'failed') {
        nextStatus = {
          state: 'error',
          message: result?.message || 'Unable to send report by email or Slack.',
        }
        toast.error(nextStatus.message)
      } else {
        const sent = Boolean(result?.ok)
        nextStatus = {
          state: sent ? 'success' : 'error',
          message: result?.message || reportText || 'Report delivery status unavailable.',
        }
        if (sent) {
          toast.success(nextStatus.message)
        } else {
          toast.error(nextStatus.message)
        }
      }

      setReportStatus(nextStatus)

      return {
        ok: nextStatus.state !== 'error',
        data,
      }
    } catch {
      const nextStatus = {
        state: 'error',
        message: 'Unable to send doctor report notification.',
      }
      setReportStatus(nextStatus)
      toast.error(nextStatus.message)
      return { ok: false, message: nextStatus.message }
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    setRole('patient')
    setUser(null)
    setMessages([])
    setReportStatus(null)
    const freshSessionId = createSessionId()
    setSession(freshSessionId)
    toast.success('Logged out successfully.')
  }

  const value = {
    role,
    setRole,
    user,
    setUser,
    messages,
    isLoading,
    reportStatus,
    clearReportStatus,
    sendMessage,
    sendDoctorReportNotification,
    setSlackConnected,
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
