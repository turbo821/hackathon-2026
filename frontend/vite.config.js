import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// Куда dev-сервер перенаправляет /api. В docker-compose это имя сервиса
// backend, при запуске без docker — http://localhost:5000.
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:5000'

export default defineConfig({
  plugins: [tailwindcss()],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
    // Фронт ходит в API по тому же origin (VITE_API_URL=/api/v1), а dev-сервер
    // перенаправляет эти запросы в бэкенд. Так браузеру не нужно знать адрес
    // бэкенда, и CORS не требуется: запрос идёт с того же origin, что страница.
    proxy: {
      '/api': { target: BACKEND_URL, changeOrigin: true },
    },
  },
})
