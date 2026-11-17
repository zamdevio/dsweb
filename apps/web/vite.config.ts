import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Cloudflare Pages: build → dist/, public/* copied to dist root
});
