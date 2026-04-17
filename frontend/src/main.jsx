import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { Toaster } from 'sonner'
import './index.css'
import App from './App.jsx'

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {googleClientId ? (
      <GoogleOAuthProvider clientId={googleClientId}>
        <App />
        <Toaster richColors position="top-right" />
      </GoogleOAuthProvider>
    ) : (
      <>
        <App />
        <Toaster richColors position="top-right" />
      </>
    )}
  </StrictMode>,
)
