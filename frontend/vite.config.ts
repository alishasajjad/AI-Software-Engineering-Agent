import react from '@vitejs/plugin-react'
import {
  defineConfig,
  loadEnv,
} from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(
    mode,
    process.cwd(),
    '',
  )

  const apiProxyTarget =
    env.VITE_DEV_API_PROXY_TARGET ||
    'http://127.0.0.1:8000'

  return {
    plugins: [
      react(),
    ],

    server: {
      host: '127.0.0.1',
      port: 5173,

      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },

    preview: {
      host: '127.0.0.1',
      port: 4173,
    },
  }
})
