/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const api = env.SULCO_API_PROXY || "http://127.0.0.1:8000";

  return {
    plugins: [
      // Precisa vir antes do plugin do React.
      tanstackRouter({ target: "react", autoCodeSplitting: true }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    build: {
      // O chunk do Three.js/R3F (~900 kB) é carregado sob demanda, só nas telas 3D.
      chunkSizeWarningLimit: 1000,
    },
    server: {
      // Em dev, tudo que começa com /api vai para o back-end sem o prefixo.
      proxy: {
        "/api": {
          target: api,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
