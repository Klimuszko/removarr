import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // For local dev, proxy API to backend if you run it on 8765
      '/api': 'http://localhost:8765',
      '/health': 'http://localhost:8765',
      '/webhook': 'http://localhost:8765',
    }
  }
})
