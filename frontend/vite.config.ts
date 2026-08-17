import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// https://vite.dev/config/
// 通过 loadEnv 读取对应模式（--mode xxx）的 env 文件，实现多模式代理配置
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  const proxyTarget = env.VITE_PROXY_TARGET || 'http://localhost:18000';
  const useProxy = env.VITE_USE_PROXY !== 'false'; // 默认 true（除 online 显式设 false）

  // online 模式且 VITE_USE_PROXY=false 时，关闭本地代理（直接跨域调用完整 URL）
  const proxyConfig = useProxy
    ? {
        // 将 /api 请求代理到当前模式的后端服务
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          // SSE (Server-Sent Events) 需要禁用响应缓冲
          configure: (proxy) => {
            proxy.on('proxyRes', (proxyRes) => {
              // 禁用代理的响应缓冲，确保 SSE 流式数据实时转发
              proxyRes.headers['Cache-Control'] = 'no-cache';
              proxyRes.headers['X-Accel-Buffering'] = 'no';
            });
          },
        },
      }
    : undefined;

  return {
    plugins: [react()],
    resolve: {
      alias: {
        // 路径别名：@ 指向 src 目录
        '@': path.resolve(__dirname, 'src'),
      },
    },
    define: {
      // 在构建产物中注入模式信息（可选，调试用）
      __APP_MODE__: JSON.stringify(env.VITE_RUN_MODE || mode),
    },
    server: {
      port: 38000,
      host: true,
      proxy: proxyConfig,
    },
    // 构建时可直接把完整 URL 打进去（online 模式），否则保留相对路径 /api/v1
    envPrefix: 'VITE_',
  };
});
