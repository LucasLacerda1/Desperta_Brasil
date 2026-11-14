import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Como no TaskFlow: o front chama /api e o Vite repassa para o Flask (sem CORS em desenvolvimento).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
