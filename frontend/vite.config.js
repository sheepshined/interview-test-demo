import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
const websocketTarget = backendTarget.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': { target: backendTarget, changeOrigin: true },
      '/ws': { target: websocketTarget, ws: true },
    },
  },
})
