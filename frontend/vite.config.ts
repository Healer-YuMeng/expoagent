import fs from 'fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
const rootEnvDir = path.resolve(__dirname, '..')
const envDir = fs.existsSync(path.resolve(rootEnvDir, '.env')) ? rootEnvDir : __dirname

export default defineConfig({
  plugins: [vue()],
  envDir,
  envPrefix: ['VITE_', 'tiao'],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 8006,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9008',
        changeOrigin: true,
      }
    }
  }
})
