import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // three.js and pixi.js dominate bundle size; splitting them lets the
        // app shell load first and the render engines cache independently.
        manualChunks: {
          three: ["three"],
          pixi: ["pixi.js"],
          vendor: ["react", "react-dom", "zustand"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // REST + WebSocket both proxy to the FastAPI backend in dev.
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
