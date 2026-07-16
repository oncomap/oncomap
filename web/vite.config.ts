/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static-export SPA: builds to web/dist/, which scripts/build_site.sh copies into
// _site/ alongside the compiled site.json. Deep links rely on the host SPA
// fallback (see the _redirects file written by build_site.sh).
export default defineConfig({
  plugins: [react()],
  // Hardened production output: minified bundle, no source maps (never ship a
  // map that reconstructs our source), and HTML/JS comments stripped - so the
  // served page exposes no readable source or hints for an attacker to probe.
  build: {
    outDir: "dist",
    sourcemap: false,
    minify: "esbuild",
  },
  esbuild: {
    legalComments: "none",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
