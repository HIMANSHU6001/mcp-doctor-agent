import { useEffect, useRef, useState } from 'react'
import { Activity, Loader2, LogOut, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import { useApp } from '../context/AppContext'
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Input } from './ui/input'

const ChatScreen = () => {
  const { user, role, messages, isLoading, sendMessage, logout } = useApp()
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!input.trim() || isLoading) {
      return
    }
    sendMessage(input.trim())
    setInput('')
  }

  const handleDailyStats = () => {
    sendMessage('Generate my daily stats report for today')
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
          <Button variant="outline" size="sm" onClick={handleDailyStats} className="gap-2">
            <Activity className="h-4 w-4" />
            Generate Daily Stats
          </Button>
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
