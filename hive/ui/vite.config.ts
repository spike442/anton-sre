import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const uiRoot = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: uiRoot,
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 8080,
    strictPort: true,
  },
});
