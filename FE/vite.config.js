// FE/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const target = (process.env.VITE_API_URL || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    hmr: {
      protocol: "wss",
      host: "65f2f4ae-a5b5-4f68-b2f6-2253fc571dd7-00-mog1t9mu62qx.pike.replit.dev", // ★ 포트없이
      clientPort: 443, // ★ wss는 443
    },
    proxy: {
      "^/api": {
        target,
        changeOrigin: true,
        secure: true,
        ws: true,
      },
    },
    allowedHosts: [".replit.dev", ".pike.replit.dev", ".repl.co"],
  },
});
