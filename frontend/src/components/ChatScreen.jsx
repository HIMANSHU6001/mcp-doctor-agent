import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  Bot,
  Calendar,
  Check,
  HeartPulse,
  Link2,
  Loader2,
  LogOut,
  Send,
  Stethoscope,
  Users,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { toast } from 'sonner'

import { useApp } from '../context/AppContext'
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Textarea } from './ui/textarea'
import { cn } from '../lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const SLACK_CLIENT_ID = import.meta.env.VITE_SLACK_CLIENT_ID || ''

const PATIENT_SUGGESTIONS = [
  { icon: Calendar, label: 'Book an appointment', prompt: 'I would like to book an appointment.' },
  { icon: Users, label: 'List available doctors', prompt: 'Please list available doctors.' },
]

const DOCTOR_SUGGESTIONS = [
  { icon: Calendar, label: 'My schedule', prompt: 'Show my schedule for today.' },
  { icon: Activity, label: 'Daily stats', prompt: 'Generate my daily stats report for today.' },
]

const ChatScreen = () => {
  const {
    user,
    role,
    messages,
    isLoading,
    reportStatus,
    clearReportStatus,
    sendMessage,
    setSlackConnected,
    logout,
  } = useApp()
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)

  const slackConnected = Boolean(user?.slackConnected)
  const suggestions = role === 'doctor' ? DOCTOR_SUGGESTIONS : PATIENT_SUGGESTIONS

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) {
      return
    }
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
  }, [input])

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

  const submit = (text) => {
    if (!text.trim() || isLoading) {
      return
    }
    clearReportStatus()
    sendMessage(text.trim())
    setInput('')
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    submit(input)
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit(input)
    }
  }

  const handleConnectSlack = () => {
    if (slackConnected) {
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
    <div className="flex h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur-md sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-600 text-white shadow-sm">
            <Stethoscope className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-base font-bold leading-tight text-slate-900 sm:text-lg">MediAgent AI</h1>
            <p className="hidden text-xs text-slate-500 sm:block">Your medical assistant</p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <Badge variant="secondary" className="capitalize">{role}</Badge>

          {role === 'doctor' && (
            <Button
              variant={slackConnected ? 'secondary' : 'outline'}
              size="sm"
              onClick={handleConnectSlack}
              disabled={slackConnected}
              className={cn(
                'gap-2',
                slackConnected && 'bg-slate-100 text-slate-900 hover:bg-slate-100 disabled:opacity-100',
              )}
            >
              {slackConnected ? <Check className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
              <span className="hidden sm:inline">{slackConnected ? 'Slack Connected' : 'Connect Slack'}</span>
            </Button>
          )}

          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarImage src={user?.picture || ''} alt={user?.name || 'User'} />
              <AvatarFallback>{user?.name?.charAt(0) || 'U'}</AvatarFallback>
            </Avatar>
            <span className="hidden text-sm font-medium text-slate-700 md:inline">{user?.name || 'User'}</span>
          </div>

          <Button variant="ghost" size="sm" onClick={logout} aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 sm:p-6">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center gap-6 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
              <Bot className="h-8 w-8" />
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-semibold text-slate-900">
                Hi {user?.name?.split(' ')[0] || 'there'}, how can I help you today?
              </h2>
              <p className="text-sm text-slate-500">Pick a suggestion or type your own question.</p>
            </div>
            <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-3">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion.label}
                  onClick={() => submit(suggestion.prompt)}
                  className="group flex flex-col items-start gap-2 rounded-xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-sky-300 hover:bg-sky-50/60 hover:shadow-sm"
                >
                  <suggestion.icon className="h-5 w-5 text-sky-600" />
                  <span className="text-sm font-medium text-slate-900">{suggestion.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={cn('flex items-end gap-2', message.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                {message.role === 'assistant' && (
                  <Avatar className="h-7 w-7 shrink-0 bg-sky-100">
                    <AvatarFallback className="bg-sky-100 text-sky-700">
                      <Bot className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                )}
                <div
                  className={cn(
                    'group max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm',
                    message.role === 'user'
                      ? 'rounded-br-md bg-sky-600 text-white'
                      : 'rounded-bl-md border border-slate-200 bg-white text-slate-800',
                  )}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose prose-sm max-w-none prose-p:my-1">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <span className="whitespace-pre-wrap">{message.content}</span>
                  )}
                </div>
                {message.role === 'user' && (
                  <Avatar className="h-7 w-7 shrink-0">
                    <AvatarImage src={user?.picture || ''} alt={user?.name || 'User'} />
                    <AvatarFallback className="text-xs">{user?.name?.charAt(0) || 'U'}</AvatarFallback>
                  </Avatar>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="flex items-end gap-2">
                <Avatar className="h-7 w-7 shrink-0">
                  <AvatarFallback className="bg-sky-100 text-sky-700">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Thinking...
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {role === 'doctor' && messages.length > 0 && (
        <div className="border-t border-slate-200 bg-white/60 px-4 py-2 sm:px-6">
          <div className="mx-auto flex max-w-3xl gap-2 overflow-x-auto pb-1 [scrollbar-width:thin]">
            {DOCTOR_SUGGESTIONS.map((suggestion) => (
              <Button
                key={suggestion.label}
                variant="outline"
                size="sm"
                onClick={() => submit(suggestion.prompt)}
                disabled={isLoading}
                className="shrink-0 gap-2"
              >
                <suggestion.icon className="h-4 w-4" />
                {suggestion.label}
              </Button>
            ))}
          </div>
          {reportStatus && (
            <div className="mx-auto mt-1 max-w-3xl">
              <p
                className={cn(
                  'text-xs',
                  reportStatus.state === 'success'
                    ? 'text-emerald-700'
                    : reportStatus.state === 'loading'
                      ? 'text-slate-500'
                      : reportStatus.state === 'warning'
                        ? 'text-amber-700'
                        : 'text-red-600',
                )}
              >
                {reportStatus.message}
              </p>
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="border-t border-slate-200 bg-white p-3 sm:p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Shift+Enter for newline)"
            disabled={isLoading}
            rows={1}
            className="min-h-[44px] flex-1 resize-none rounded-xl py-3"
          />
          <Button
            type="submit"
            size="sm"
            variant="accent"
            disabled={isLoading || !input.trim()}
            className="h-11 w-11 shrink-0 rounded-xl p-0"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </form>
    </div>
  )
}

export default ChatScreen
