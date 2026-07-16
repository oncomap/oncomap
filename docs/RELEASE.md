# OncoMap - cutting a versioned release (Zenodo DOI)

asks for a reproducible, versioned release with a Zenodo DOI
(`v0.1`). The repository metadata is already prepared:

- `.zenodo.json` - the deposit metadata Zenodo reads when a GitHub release is
  published (title, description, creators, `cc-by-4.0`, version, keywords).
- `CITATION.cff` - machine-readable citation; GitHub renders a "Cite this
  repository" panel from it.

The DOI itself must be minted from **your** Zenodo account, so the final two
steps are yours; everything else is committed.

## One-time: connect the repo to Zenodo

1. Sign in at <https://zenodo.org> (via GitHub is simplest).
2. Go to <https://zenodo.org/account/settings/github/> and flip the toggle
   **on** for `oncomap/oncomap`. (Zenodo archives the tarball at release time; the deposit it
   creates is public.)

## Per release

1. Make sure `main` is green (`validate-records` CI) and the catalog compiles:
   ```bash
   uv run --locked python build/validate.py
   uv run --locked python build/compile.py
   ```
2. Optionally build the compiled data bundle to attach as release assets (the
   source tarball Zenodo archives already contains `records/` + `build/`, from
   which `dist/` is regenerable, so this is a convenience):
   ```bash
   uv run --extra build --locked python build/compile.py   # emits build/dist/
   (cd build && zip -r ../oncomap-v0.1-dist.zip dist)
   ```
3. Tag and publish the GitHub release (this is what triggers Zenodo):
   ```bash
   git tag -a v0.1.0 -m "OncoMap v0.1.0"
   git push origin v0.1.0
   gh release create v0.1.0 --title "OncoMap v0.1.0" \
     --notes "First public snapshot: 247 datasets (175 spatial-transcriptomics + 72 spatial-proteomics) across 42 cancer types, all nine spatial platforms, harvested from GEO, ArrayExpress, CZ CELLxGENE, Zenodo, HTAN, and the EBI BioImage Archive." \
     oncomap-v0.1-dist.zip   # omit the asset if you skipped step 2
   ```
4. Zenodo receives the webhook, creates the deposit from `.zenodo.json`, and
   mints the DOI (a concept DOI for all versions plus a version DOI for v0.1.0).
5. Copy the version DOI into the README badge and back into `.zenodo.json`
   `related_identifiers` (relation `isVersionOf`) for the next release.

## Keeping metadata current

Before each release bump the version in **both** `.zenodo.json` and
`CITATION.cff` (and `date-released` in the CFF), and refresh the dataset/cancer-
type counts in the `.zenodo.json` description if they have moved materially.
