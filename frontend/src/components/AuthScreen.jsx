import { GoogleLogin } from '@react-oauth/google'
import { Stethoscope, User as UserIcon } from 'lucide-react'
import { useState } from 'react'

import { useApp } from '../context/AppContext'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'

const API_BASE = 'http://localhost:8000'

const AuthScreen = () => {
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const { role, setRole, setUser } = useApp()
  const [isAuthenticating, setIsAuthenticating] = useState(false)

  const handleGoogleSuccess = async (credentialResponse) => {
    const token = credentialResponse?.credential
    if (!token) {
      return
    }

    setIsAuthenticating(true)

    try {
      const response = await fetch(`${API_BASE}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      })

      if (!response.ok) {
        throw new Error('Google sign-in failed')
      }

      const data = await response.json()
      setUser({
        name: data.name,
        email: data.email,
        picture: data.picture ?? null,
      })
    } finally {
      setIsAuthenticating(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-sky-50 via-white to-teal-50 p-4">
      <Card className="w-full max-w-md shadow-lg shadow-sky-100/60">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-sky-600">
            <Stethoscope className="h-7 w-7 text-white" />
          </div>
          <CardTitle className="text-2xl font-bold">MediAgent AI</CardTitle>
          <CardDescription>Your intelligent medical assistant</CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <div>
            <p className="mb-3 text-center text-sm font-medium text-slate-500">I am a...</p>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setRole('patient')}
                className={`flex flex-col items-center gap-2 rounded-xl border-2 p-5 transition-all ${
                  role === 'patient'
                    ? 'border-sky-500 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-500 hover:border-sky-300'
                }`}
              >
                <UserIcon className="h-8 w-8" />
                <span className="text-sm font-semibold">Patient</span>
              </button>
              <button
                type="button"
                onClick={() => setRole('doctor')}
                className={`flex flex-col items-center gap-2 rounded-xl border-2 p-5 transition-all ${
                  role === 'doctor'
                    ? 'border-sky-500 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-500 hover:border-sky-300'
                }`}
              >
                <Stethoscope className="h-8 w-8" />
                <span className="text-sm font-semibold">Doctor</span>
              </button>
            </div>
          </div>

          {googleClientId ? (
            isAuthenticating ? (
              <Button className="h-12 w-full text-base" disabled size="lg" variant="accent">
                Verifying Google account...
              </Button>
            ) : (
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => {
                    setIsAuthenticating(false)
                  }}
                  text="signin_with"
                  shape="rectangular"
                  theme="filled_blue"
                  size="large"
                />
              </div>
            )
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              Set VITE_GOOGLE_CLIENT_ID in frontend/.env to enable Google sign-in.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default AuthScreen
