import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Build into the Django app's static dir so collectstatic works unchanged.
// The manifest lets the Django view resolve the hashed filenames.
export default defineConfig({
  plugins: [react()],
  base: "/static/app/",
  build: {
    outDir: resolve(__dirname, "../backend/portfolio/static/app"),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: { input: resolve(__dirname, "src/main.jsx") },
  },
  // fs.allow: the shared design system lives outside the Vite root.
  server: {
    fs: { allow: [resolve(__dirname, ".."), __dirname] },
    port: 5173,
    strictPort: true,
    cors: true,
    // Django serves the shell at :8000 and proxies nothing; the app calls the
    // API there directly.
    origin: "http://localhost:5173",
  },
});
