import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/ask': 'http://127.0.0.1:8000',
      '/memory': 'http://127.0.0.1:8000',
      '/debug-prompt': 'http://127.0.0.1:8000',
    },
  },
})

