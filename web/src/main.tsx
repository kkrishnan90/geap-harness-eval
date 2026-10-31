import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { initMode } from './lib/api'
import { initMe } from './lib/auth'
import App from './App'

initMode()
  .then((m) => initMe(m))
  .then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
