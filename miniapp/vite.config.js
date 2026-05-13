/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // v1.26 Phase 83 (TEST-01): Vitest + React Testing Library safety net.
  // See .planning/phases/83-vitest-rtl-foundation/83-CONTEXT.md for rationale.
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
    include: [
      'src/**/__tests__/**/*.{js,jsx}',
      'src/**/*.test.{js,jsx}',
    ],
    css: false, // speed — snapshot tests assert structure, not CSS
  },
})
// Trigger Vercel rebuild
