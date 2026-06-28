import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
  ],
  server: {
    proxy: {
      '/events': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (_proxyRes, _req, res) => {
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
          });
        },
      },
      '/fighters': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (_proxyRes, _req, res) => {
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
          });
        },
      },
      '/fights': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // The client-side route `/fights/:id` collides with this proxy path.
        // On a full-page reload the browser requests `/fights/:id` with an
        // `Accept: text/html` header — serve the SPA instead of proxying so
        // React Router can handle the route. API calls use fetch() (Accept: */*)
        // and fall through to the backend as normal.
        bypass: (req) => {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html';
          }
        },
        configure: (proxy) => {
          proxy.on('proxyRes', (_proxyRes, _req, res) => {
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
            res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
          });
        },
      },
    },
  },
})
