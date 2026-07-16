<!-- Thanks for contributing to OncoMap. Keep PRs small: ideally one study (its
dataset record(s) + paper node) or one tooling change. -->

## What this changes

<!-- One or two lines. Link the "Add a dataset" issue if this fills one. -->

Closes #

## Type

- [ ] New/updated dataset record(s)
- [ ] New/updated paper / method / group node
- [ ] Tooling (build / harvester / vocab / site)
- [ ] Docs

## Curation checklist (for record changes)

<!-- The trust gate is enforced in CI, but confirm you did the human checks. -->

- [ ] `uv run python build/validate.py` passes (schema + trust gate + referential integrity + vocab membership).
- [ ] `cancer_type` is a valid OncoTree code and matches the study; `tissue` is a valid UBERON term in the seed.
- [ ] `platform` is the spatial **assay** confirmed from the sample/methods text (not the sequencer).
- [ ] The samples are human tumour tissue (no mouse/PDX/organoid/cell-line-only data).
- [ ] `access` reflects the true file access at source (open vs on_request/controlled).

## For a `verified` record, additionally

- [ ] The accession resolves live (`uv run python build/check_accessions.py --status verified`).
- [ ] `source_paper` links a real publication node, and `last_verified` is set.

<!-- Records that don't yet meet the verified bar are welcome at machine_draft /
human_reviewed - the trust tier is honest, not a blocker. -->
