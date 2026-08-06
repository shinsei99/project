import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// base を相対パス './' にすることで、GitHub Pages のサブディレクトリ配信と
// Capacitor（iOS の file:// 配信）の両方でアセットが正しく解決される。
export default defineConfig({
  base: './',
  plugins: [react()],
})
