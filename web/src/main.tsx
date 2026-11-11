import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { z } from "zod"

import "@/styles/globals.css"
import { App } from "@/app/app"

// The page forbids eval (its content security policy); zod is told not to try it.
z.config({ jitless: true })

const root = document.getElementById("root")
if (!root) throw new Error("index.html has no #root element")

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
)
