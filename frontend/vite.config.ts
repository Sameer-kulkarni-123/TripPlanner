import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development every API call goes to /__backend/... and Vite forwards it to FastAPI,
// so the browser never needs CORS. Point BACKEND_URL elsewhere if uvicorn runs on another port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.BACKEND_URL || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/__backend": {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/__backend/, ""),
        },
      },
    },
  };
});
