// Copy the compiled catalog payload into web/public so the dev server and the
// Vite build both serve it at /site.json. Records -> build/compile.py ->
// build/dist/site.json stays the single source of truth; this only mirrors it.
import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../build/dist/site.json");
const destDir = resolve(here, "../public");
const dest = resolve(destDir, "site.json");

if (!existsSync(src)) {
  console.warn(
    `[copy-site-json] ${src} not found. Run 'uv run python build/compile.py' first.`,
  );
  process.exit(0);
}
mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`[copy-site-json] ${src} -> ${dest}`);
