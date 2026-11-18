import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Como no TaskFlow: o front chama /api e o Vite repassa para o Flask (sem CORS em desenvolvimento).
export default defineConfig({
  // Tailwind CSS (framework de CSS) gera so as classes usadas no site
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
