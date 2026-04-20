import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  root: resolve('./frontend'),
  base: '/static/dist/',
  build: {
    outDir: resolve('./static/dist'),
    assetsDir: '',
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve('./frontend/src/main.js'),
        style: resolve('./frontend/src/style.css'),
      },
    },
  },
  server: {
    origin: 'http://localhost:5173',
  },
});