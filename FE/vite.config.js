// FE/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173, // 프론트 고정
    hmr: { 
      protocol: "ws", 
      host: "localhost", 
      port: 5173 
    }, // WebSocket 프로토콜 수정
    proxy: {
      "^/api": {
        // FE가 API 부를 땐 프록시로 내부 8000 사용
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },
    allowedHosts: [".replit.dev", ".pike.replit.dev", ".repl.co"],
  },
});
