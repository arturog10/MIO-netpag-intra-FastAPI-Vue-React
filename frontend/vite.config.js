import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Redirige cualquier petición que comience con /api
      '/api': {
        // A tu servidor backend local (FastAPI/Uvicorn)
        target: 'http://127.0.0.1:8001',
        
        // Esto es importante para evitar errores de CORS en desarrollo
        changeOrigin: true,
      }
    }
  }
})
