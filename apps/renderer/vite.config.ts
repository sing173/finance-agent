import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: './',  // Electron需要相对路径
  resolve: {
    alias: {
      '@shared': path.resolve(process.cwd(), '../../shared'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
