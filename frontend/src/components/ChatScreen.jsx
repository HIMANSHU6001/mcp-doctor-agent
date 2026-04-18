import { useEffect, useRef, useState } from 'react'
import { Activity, CheckCircle2, Link2, Loader2, LogOut, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { toast } from 'sonner'

import { useApp } from '../context/AppContext'
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const SLACK_CLIENT_ID = import.meta.env.VITE_SLACK_CLIENT_ID || ''

const ChatScreen = () => {
  const {
    user,
    role,
    messages,
    isLoading,
    reportStatus,
    clearReportStatus,
    sendMessage,
    sendDoctorReportNotification,
    setSlackConnected,
    logout,
  } = useApp()
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const slackConnected = params.get('slack_connected')
    const slackError = params.get('slack_error')

    if (!slackConnected && !slackError) {
      return
    }

    if (slackConnected === 'true') {
      setSlackConnected(true)
      toast.success('Successfully connected to Slack.')
    } else {
      setSlackConnected(false)
      const readableError = slackError ? slackError.replaceAll('_', ' ') : 'unknown error'
      toast.error(`Failed to connect Slack: ${readableError}`)
    }

    const cleanUrl = `${window.location.pathname}${window.location.hash || ''}`
    window.history.replaceState({}, document.title, cleanUrl)
  }, [setSlackConnected])

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!input.trim() || isLoading) {
      return
    }
    clearReportStatus()
    sendMessage(input.trim())
    setInput('')
  }

  const handleDailyStats = async () => {
    await sendDoctorReportNotification()
  }

  const handleConnectSlack = () => {
    if (user?.slackConnected) {
      return
    }
    
    if (!SLACK_CLIENT_ID) {
      toast.error('Slack is not configured. Set VITE_SLACK_CLIENT_ID in frontend environment.')
      return
    }
    
    if (!user?.email) {
      toast.error('User email not available. Please log in again.')
      return
    }
    
    const redirectUri = `${API_BASE}/api/auth/slack/callback`
    const slackAuthUrl = new URL('https://slack.com/oauth/v2/authorize')
    slackAuthUrl.searchParams.set('client_id', SLACK_CLIENT_ID)
    slackAuthUrl.searchParams.set('scope', 'chat:write,users:read.email,users:read')
    slackAuthUrl.searchParams.set('redirect_uri', redirectUri)
    slackAuthUrl.searchParams.set('state', user.email)
    
    window.location.assign(slackAuthUrl.toString())
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-teal-50 px-3 py-3 sm:px-6 sm:py-4 lg:px-10 xl:px-14">
      <div className="mx-auto flex h-[calc(100vh-1.5rem)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200/70 bg-white/65 shadow-sm backdrop-blur">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white/70 px-4 py-3 sm:px-6">
        <h1 className="text-lg font-bold text-slate-900">MediAgent AI</h1>
        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="capitalize">{role}</Badge>
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarImage src={user?.picture || ''} alt={user?.name || 'User'} />
              <AvatarFallback>{user?.name?.charAt(0) || 'U'}</AvatarFallback>
            </Avatar>
            <span className="hidden text-sm font-medium text-slate-700 sm:inline">{user?.name}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} className="gap-2" aria-label="Log out">
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Log out</span>
          </Button>
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-slate-400">
            <Activity className="h-12 w-12 opacity-40" />
            <p className="text-sm">Start a conversation with MediAgent AI</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                message.role === 'user'
                  ? 'rounded-br-md bg-sky-600 text-white'
                  : 'rounded-bl-md border border-sky-100 bg-white text-slate-800'
              }`}
            >
              {message.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-strong:text-slate-900">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              ) : (
                message.content
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md border border-sky-100 bg-white px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking...
              </div>
            </div>
          </div>
        )}
      </div>

      {role === 'doctor' && (
        <div className="border-t border-slate-200 bg-white/60 px-4 py-2 sm:px-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Button
                variant={user?.slackConnected ? 'secondary' : 'outline'}
                size="sm"
                onClick={handleConnectSlack}
                className="gap-2"
                disabled={Boolean(user?.slackConnected)}
              >
                {user?.slackConnected ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <Link2 className="h-4 w-4" />
                )}
                {user?.slackConnected ? 'Connected to Slack' : 'Connect to Slack'}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={handleDailyStats}
                className="gap-2"
                disabled={isLoading}
              >
                <Activity className="h-4 w-4" />
                Send Daily Report
              </Button>
            </div>
            {reportStatus && (
              <p
                className={`text-xs ${
                  reportStatus.state === 'success'
                    ? 'text-emerald-700'
                    : reportStatus.state === 'loading'
                      ? 'text-slate-500'
                      : reportStatus.state === 'warning'
                        ? 'text-amber-700'
                      : 'text-red-600'
                }`}
              >
                {reportStatus.message}
              </p>
            )}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="border-t border-slate-200 bg-white/70 p-4 sm:px-6">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" size="sm" variant="accent" disabled={isLoading || !input.trim()} className="px-3">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
      </div>
    </div>
  )
}

export default ChatScreen
