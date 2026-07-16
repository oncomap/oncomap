#!/usr/bin/env bash
# Build the static browsable view for a host (Netlify / Cloudflare Pages).
# Compiles records -> site.json, builds the Vite/React app, and assembles the
# publish dir _site/ (built app + the fresh payload + SPA fallback). Used as the
# host's build command; also works locally. Node and Python are both build deps.
set -euo pipefail

# 1. Compile the catalog payload (records are the source of truth).
python3 -m pip install --quiet --disable-pip-version-check jsonschema pyyaml
python3 build/compile.py

# 2. Build the React app (its prebuild step mirrors build/dist/site.json into
#    web/public so Vite bundles it).
pushd web >/dev/null
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build
popd >/dev/null

# 3. Assemble _site/ = built app + authoritative site.json + SPA fallback.
rm -rf _site
mkdir -p _site
cp -R web/dist/. _site/
cp build/dist/site.json _site/site.json
printf '/*    /index.html   200\n' >_site/_redirects

echo "Built _site/ ($(ls _site | tr '\n' ' '))"
