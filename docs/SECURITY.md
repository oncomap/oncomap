# OncoMap - Security & Data-Classification Policy

OncoMap is a metadata catalog, not a data host, so its trust boundary is
narrow - but it is real: source-registry credentials, contributor identity, and
the hard line against ingesting controlled-access data. This document is the
lightweight threat model, the data-classification policy, and the secrets
procedure.

Companion: `docs/DATA_SOURCES.md §8` (access & compliance notes),
`docs/OncoMap-SPEC.md §5` (curation trust gate).

---

## 1. Data-classification policy (the load-bearing rule)

Every dataset OncoMap catalogs is classified by the **access** of its underlying
data. This single field governs what we are allowed to store.

| Class (`access`) | What it means                             | What OncoMap stores                                                                     | Never stores                                                                |
| ---------------- | ----------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `open`           | Public, no auth to retrieve               | Full metadata **+ resolvable accession/DOI links**                                      | The primary data itself                                                     |
| `controlled`     | Requires approval (dbGaP, some HTAN/TCGA) | Metadata **+ a pointer + the access mechanism** (e.g. "dbGaP phsXXXXXX; apply via DAC") | Any resolvable link to the protected payload, credentials, or mirrored data |
| `on_request`     | Available by contacting the authors       | Metadata + contact route noted in `reuse_notes`                                         | Mirrored data                                                               |

**Bright line:** _only `access: open` data is ever cataloged with a resolvable
link._ Controlled-access datasets are recorded as **pointers with the
access-mechanism noted, never mirrored** (DATA_SOURCES §8).

**Corollaries**

- OncoMap never re-hosts or re-processes primary data (SPEC §2, out-of-scope).
- No clinical or patient-identifiable data enters a record - not in `title`,
  `reuse_notes`, or any field. Records describe _datasets_, not subjects.
- A record's `accession` list for a `controlled` dataset holds the **registry
  pointer** (e.g. `phs001234`), which is itself public metadata - not a data URL.

---

## 2. Lightweight threat model

Scope is a public, versioned metadata repository built by machine-draft +
human-review, published to GitHub and (later) Zenodo/Pages.

| #   | Threat                                                | Vector                                                         | Mitigation                                                                                                                                                                      |
| --- | ----------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1  | **Controlled-access data leaks into the catalog**     | A curator/extractor pastes protected content or a working link | Data-classification policy (§1); `access` is required by schema; review gate (SPEC §5); PR review checks class before merge                                                     |
| T2  | **Secret committed to git**                           | API key in a record, script, or `.env`                         | `.env` gitignored; `.env.example` only; secret-scan hook on edits; pre-commit `check-added-large-files` + secret patterns; secrets live in the environment, never in `records/` |
| T3  | **Machine-drafted junk erodes trust**                 | Hallucinated accession / wrong platform merged as fact         | Nothing ships `verified` without human review **and** a resolvable accession (SPEC §5, enforced structurally in `build/validate.py`)                                            |
| T4  | **Supply-chain / dependency tampering**               | Malicious transitive dep in the tiny Python toolchain          | Deps pinned via `uv.lock`; minimal dependency surface (jsonschema, pyyaml); Dependabot/`uv lock` review on bumps                                                                |
| T5  | **Source-registry credential abuse / rate-limit ban** | Key checked into a public repo, or unthrottled scraping        | Keys in env only (T2); respect documented rate limits (§4); read-only tokens with least scope                                                                                   |
| T6  | **Malicious contribution via PR**                     | Poisoned record or workflow change from a fork                 | CI runs validation on PRs; workflow changes require maintainer review; no secrets exposed to `pull_request` from forks                                                          |

Out of threat scope (by design): DDoS/availability of a live service (there is
none - artifacts are static), and anything touching primary data (never held).

---

## 3. Secrets procedure

**What needs secrets:** querying source registries during extraction and
verification - **not** publishing (the catalog itself is public metadata).

- Credentials live **only** in a local, gitignored `.env` (template:
  `.env.example`) or in CI/GitHub Actions **encrypted secrets** - never in
  `records/`, `schema/`, `vocab/`, or any tracked file.
- Tokens are **read-only** and least-scope (e.g. an NCBI key for rate, not
  write access).
- Rotate on suspected exposure; if a secret is ever committed, treat the key as
  compromised - **rotate first**, then scrub history.
- The provisioned keys (see `.env.example`): `NCBI_API_KEY`,
  `SYNAPSE_AUTH_TOKEN`, `ZENODO_TOKEN`.

## 4. Rate limits & source etiquette

- **NCBI E-utilities:** ≤ 3 req/s without a key, ≤ 10 req/s with
  `NCBI_API_KEY`. Extraction tooling must throttle and back off.
- **Synapse / BigQuery (HTAN):** require auth; used read-only for metadata.
- **OLS4 / OncoTree:** used only by `vocab/build_vocab.py` at snapshot-refresh
  time, not per-record - negligible load.

## 5. Contributor identity & provenance

- Contributions arrive as GitHub PRs; authorship is the git identity.
- Curation status changes (`machine_draft → human_reviewed → verified`) are
  traceable through commit history and PR review - the human gate is auditable.
- `last_verified` records when a `verified` record's accession was last
  confirmed resolvable, making staleness visible (SPEC §7 metadata-rot guard).

---

## 6. Enforcement status

| Control                                                            | Mechanism                                    | Status                                                                     |
| ------------------------------------------------------------------ | -------------------------------------------- | -------------------------------------------------------------------------- |
| `access` present on every dataset                                  | JSON Schema (`required`)                     | ✅ enforced                                                                |
| `verified` ⇒ resolvable accession + `last_verified` + source paper | `build/validate.py` Layer 2                  | ✅ structural (live dead-link check)                            |
| No secrets in tracked files                                        | `.gitignore` + `.env.example`                | ✅ in place                                                                |
| Secret-pattern / large-file scan on commit                         | pre-commit hooks (`.pre-commit-config.yaml`) | 🟡 large-file + yaml/json checks active; dedicated secret-scan hook to add |
| Controlled-data bright line                                        | This policy + PR review                      | 🟡 policy + human review (no automated content classifier)                 |

Gaps are intentional and phase-appropriate for a metadata repo; they are logged
here rather than silently skipped.

---

## 7. Web application security (the browsable site)

The browsable site (`web/`, a Vite/React single-page app, static-exported to
Netlify/Cloudflare) is a public, read-only view over `site.json` with one
interactive surface: the `/contact` form. There are no accounts, no session, no
server, and no database, so server-side classes (injection, broken auth, SSRF)
do not apply. The realistic surface is client-side: XSS, clickjacking,
referrer/data leakage, contact-form abuse, and build/test supply chain.

**Already safe (audited).** No `dangerouslySetInnerHTML` / `innerHTML` / `eval`
anywhere in `web/src` - all output goes through React's escaping JSX; the SVG
charts render from numeric data only, and `useHead` sets `document.title`/meta
by property assignment, not markup. Data is same-origin and build-time
(`site.json` from `build/compile.py`). Outbound links are validated:
`accessionLink()` (`web/src/lib/format.ts`) only emits known accession-scheme
URLs or an explicit `https?://`, so no `javascript:`/`data:` link can be produced
from record data, and every `target="_blank"` carries `rel="noopener
noreferrer"`. No secrets ship in the bundle (the contact form uses Netlify Forms,
which needs no client key).

**HTTP security headers** (`web/public/_headers`, shipped in the publish root and
honoured by Netlify and Cloudflare):

- Content-Security-Policy `default-src 'self'; script-src 'self'; style-src
'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src
'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src
'none'`. The production build ships no inline scripts and calls no external
  endpoints, so `script-src`/`connect-src` stay `'self'`; `style-src
'unsafe-inline'` is required for React inline styles (an accepted trade-off with
  no HTML-injection sink to exploit it); `img-src data:` covers the blank favicon
  and CSS chevrons. Validated against the production build with no CSP violations.
- Strict-Transport-Security `max-age=31536000; includeSubDomains; preload`;
  X-Frame-Options `DENY` (+ CSP `frame-ancestors 'none'`); X-Content-Type-Options
  `nosniff`; Referrer-Policy `strict-origin-when-cross-origin`; Permissions-Policy
  disabling geolocation/microphone/camera.

**Contact-form anti-abuse** (deliberately captcha-free, to avoid friction for
researchers/clinicians): a hidden honeypot (`botcheck`, dropped client-side and
by Netlify), a 30-second client-side submit cooldown against rapid-fire
re-submits, required-field + email validation before any POST, and Netlify Forms
spam filtering. Per-IP rate limiting and abuse handling are Netlify's layer (the
site has no server of its own).

**Dependency posture.** Production runtime is only React 18, React DOM 18 and
React Router 6 (charts are hand-rolled - no charting library). `npm audit`
reports a dev-only advisory (esbuild `<=0.24.2`, GHSA-67mh-4wv8-2f99, moderate)
reachable through Vite/Vitest; `npm ls --omit=dev` confirms none of these appear
in the production dependency tree, so the deployed static site has no exposure.
The advisory concerns the local dev server; the only fix is a breaking Vite major
upgrade, deferred until a non-breaking path exists.

**Testing.** The landing page and pure helpers are covered by a Vitest + Testing
Library suite (`web/src/**/*.test.ts(x)`), run in CI (the `web-tests` job in
`.github/workflows/validate.yml`).

## Reporting a vulnerability

Report suspected security issues privately by email to <security@oncomap.org>,
via a GitHub security advisory on <https://github.com/oncomap/oncomap>
(Security -> Report a vulnerability), or through the contact form at
<https://www.oncomap.org/contact>. Please do not open a public issue for a
security report.
