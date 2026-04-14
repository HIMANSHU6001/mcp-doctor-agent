import AuthScreen from './components/AuthScreen'
import ChatScreen from './components/ChatScreen'
import { AppProvider, useApp } from './context/AppContext'

function AppRouter() {
  const { user } = useApp()
  return user ? <ChatScreen /> : <AuthScreen />
}

function App() {
  return (
    <AppProvider>
      <AppRouter />
    </AppProvider>
  )
}

export default App
