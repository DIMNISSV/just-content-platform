import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
    plugins: [vue()],

    root: resolve(__dirname, './frontend'),

    // ← Это критично для HMR и django-vite
    base: '/static/',

    build: {
        outDir: resolve(__dirname, './static/dist'),
        assetsDir: '',
        manifest: true,
        emptyOutDir: true,
        rollupOptions: {
            input: {
                main: resolve(__dirname, './frontend/src/main.js'),
            },
        },
    },

    server: {
        host: '127.0.0.1',
        port: 5173,
        strictPort: true,
        cors: true,
        origin: 'http://127.0.0.1:5173',
        // Добавь это, чтобы помочь с путями
        hmr: {
            protocol: 'ws',
            host: '127.0.0.1',
            port: 5173,
        },
    },
});