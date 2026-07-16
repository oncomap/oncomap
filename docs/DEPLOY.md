# OncoMap - deploying the browsable view to oncomap.org

The browsable view (a Vite/React app under `web/`) is hosted for free from this
repo via a static host (Netlify or Cloudflare Pages), served at
**www.oncomap.org** (the apex `oncomap.org` redirects there). Both run the same
build (`scripts/build_site.sh`): compile records -> `site.json`, build the React
app, assemble the static `_site/` (built app + payload + SPA `_redirects`),
publish. The build needs **both Node and Python** on the build image (host
defaults are fine). Every push to `main` triggers an automatic rebuild.

GitHub Pages is not used: the site needs a Node + Python build step (compiling
records into `site.json`) that Pages' static build doesn't run.

---

## Option A - Netlify (build config is committed)

`netlify.toml` already sets the build command and publish dir, so setup is just
connecting the repo.

1. netlify.com -> **Add new site** -> **Import an existing project** ->
   **GitHub** -> authorize -> pick `oncomap/oncomap`.
2. Netlify reads `netlify.toml`, so leave build settings as detected
   (command `bash scripts/build_site.sh`, publish `_site`). Deploy.
3. The site goes live at `https://<random-name>.netlify.app`. Confirm it renders.
4. **Domains** -> **Add a domain** -> `oncomap.org`. Netlify shows the exact DNS
   records to add at your registrar. Typical values:
   - Apex `oncomap.org`: `A` record -> `75.2.60.5` (or use Netlify DNS by
     pointing your nameservers, which Netlify will offer - simplest for apex).
   - `www.oncomap.org`: `CNAME` -> `<random-name>.netlify.app`.
5. Netlify provisions HTTPS (Let's Encrypt) automatically once DNS resolves.

## Option B - Cloudflare Pages (dashboard settings)

Best if your DNS is already on Cloudflare (custom domain wiring is automatic).

1. Cloudflare dashboard -> **Workers & Pages** -> **Create** -> **Pages** ->
   **Connect to Git** -> authorize -> pick `oncomap/oncomap`.
2. Build settings:
   - Framework preset: **None**
   - Build command: `bash scripts/build_site.sh`
   - Build output directory: `_site`
   - Environment variables: `PYTHON_VERSION = 3.12`, `NODE_VERSION = 20`
3. Save and Deploy. Confirm it renders at `https://<project>.pages.dev`.
4. **Custom domains** -> **Set up a domain** -> `oncomap.org`.
   - If the domain's DNS is on Cloudflare: the record is created automatically.
   - If DNS is elsewhere: add a `CNAME` (apex via CNAME flattening, and `www`)
     pointing to `<project>.pages.dev`.

---

## Notes

- **Rebuild on data changes:** both hosts rebuild on every push to `main`, so a
  merged record edit redeploys the site within a minute or two.
- **What gets published:** only the compiled `_site/` (static HTML/CSS/JS +
  `site.json`). No records, schemas, or tooling are served.
- **Security headers:** `web/public/_headers` ships in the publish root
  (`_site/_headers`) and is honoured by **both** Netlify and Cloudflare Pages. It
  sets a Content-Security-Policy, HSTS, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy and Permissions-Policy. See `docs/SECURITY.md` for the rationale
  (notably the `style-src 'unsafe-inline'` needed by React inline styles). Also
  enable Netlify Forms **spam filtering** in the dashboard.
- **Contact form:** the `/contact` page uses **Netlify Forms** - no third-party
  service or client-side key. Netlify detects the form from a hidden static stub
  in `web/index.html` at build time; the React page submits to it via AJAX.
  Submissions land in the Netlify dashboard under **Forms**; to have them arrive
  in the `@oncomap.org` inbox, add an email notification under
  **Site configuration -> Forms -> Notifications -> Add notification -> Email
  notification** and set the recipient. (Form handling is Netlify-only; if the
  site is moved to the Cloudflare Pages option above, the form needs a different
  backend - e.g. a serverless function or a `mailto:` link.)
- **`www` vs apex:** the primary is **`www.oncomap.org`**; set the apex
  `oncomap.org` to redirect to it (both hosts do this in their domain settings).
- **Local preview:** for development, `npm --prefix web run dev` (its prebuild
  step mirrors `build/dist/site.json` into `web/public`, so run
  `uv run python build/compile.py` first). For a production check, run
  `bash scripts/build_site.sh` and serve `_site/`.
