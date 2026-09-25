import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 开发态禁止磁盘强缓存：重启后旧 deps 与 Chrome 缓存错位会触发 ERR_CACHE_READ_FAILURE
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        // 后端挂掉时避免静默 500，终端给出明确提示
        configure: (proxy) => {
          proxy.on('error', (_err, _req, res) => {
            console.error(
              '[vite proxy] 无法连接后端 http://127.0.0.1:8001 — 请先运行 scripts/start-dev.bat 或启动 uvicorn',
            )
            if (res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
              res.end(
                JSON.stringify({
                  detail:
                    '后端未启动或已退出（502）。请运行 intern-platform/scripts/start-dev.bat 后再刷新。',
                }),
              )
            }
          })
        },
      },
    },
  },
})
