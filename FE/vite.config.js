// FE/vite.config.js
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // 백엔드 주소 (예: https://your-backend.example.com 또는 http://127.0.0.1:8000)
  const target = (env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const isHttps = target.startsWith("https://");

  // Replit 등 외부 HMR 도메인/프로토콜/포트 (필요 시 .env에 지정)
  const HMR_HOST = env.VITE_HMR_HOST || "65f2f4ae-a5b5-4f68-b2f6-2253fc571dd7-00-mog1t9mu62qx.pike.replit.dev";
  const HMR_PROTOCOL = env.VITE_HMR_PROTOCOL || (isHttps ? "wss" : "ws");
  const HMR_CLIENT_PORT = Number(env.VITE_HMR_PORT || (isHttps ? 443 : 5173));

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      hmr: {
        protocol: HMR_PROTOCOL,
        host: HMR_HOST,
        clientPort: HMR_CLIENT_PORT,
      },
      proxy: {
        // 일반 REST/JSON API
        "^/api": {
          target,
          changeOrigin: true,
          secure: isHttps, // HTTPS 백엔드면 검증 활성
          ws: true,
          // 필요 시 백엔드가 /api 프리픽스를 안 쓴다면 아래 주석 해제
          // rewrite: (path) => path.replace(/^\/api/, ""),
        },
        // SSE 스트림 (EventSource)
        "^/react-agent": {
          target,
          changeOrigin: true,
          secure: isHttps,
          ws: false, // SSE는 WebSocket 아님
          headers: {
            Connection: "keep-alive",
          },
        },
      },
      allowedHosts: [".replit.dev", ".pike.replit.dev", ".repl.co"],
    },
  };
});
