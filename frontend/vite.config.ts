import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// หน้าเว็บถูกเสิร์ฟจาก FastAPI ที่ /app (build ไปที่ frontend/dist)
// ตอน dev (pnpm dev) ให้ proxy ไปที่ backend ที่พอร์ต 7860
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5175,
    proxy: {
      "/api": "http://127.0.0.1:7860",
      "/files": "http://127.0.0.1:7860",
      "/ws": { target: "ws://127.0.0.1:7860", ws: true },
    },
  },
});
