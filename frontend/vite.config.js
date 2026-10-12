// ============================================================
// IMPORTS
// ============================================================
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// ============================================================
// VITE CONFIGURATION
// ============================================================
// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
