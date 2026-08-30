import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 相対パス出力にしておくと、どこに置いても（GitHub Pages のサブフォルダでも）動く
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: 3005 },   // ツール分類＝LANには出さない
})
