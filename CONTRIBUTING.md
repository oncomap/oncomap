# Contributing to OncoMap

OncoMap is a curated, literature-grounded catalog of oncology spatial-omics
datasets - spatial transcriptomics and spatial proteomics. Contributions of **data** (new datasets,
corrections) and **tooling** are both welcome. The load-bearing artifact is the
curated records + schema; everything else is a thin layer over them.

## Two ways to contribute data

You do **not** need to know YAML or git to add a dataset.

1. **Open an issue** (easiest). Use the
   [**Add a dataset**](../../issues/new?template=add-a-dataset.yml) form. Its
   fields are exactly what a record needs and are fillable by reading the paper
   and its data-availability section. A curator turns your answers into a record
   and opens the PR.
2. **Open a pull request** (for curators / the git-comfortable). Add or edit the
   YAML under `records/`, run the checks below, and fill in the PR checklist.

Either way, the trust gate (below) decides how far the record advances.

## Scope

Human tumour **spatial transcriptomics**, tumour-microenvironment first. Out of
scope for now: single-cell/bulk-only studies, spatial _proteomics_ (CODEX / IMC
/ GeoMx), model systems (mouse / PDX / organoid / cell line), and non-human data.

## The data model

Four node types, one YAML file each under `records/`:

- **dataset** - a spatial dataset (accession, cancer type, tissue, platform, access, trust tier)
- **paper** - the source publication (DOI/PMID, links the datasets it produced)
- **method** - a processing pipeline (e.g. Space Ranger)
- **group** - a research group (collaboration edges are _derived_ from shared papers)

Cancer types are coded in **OncoTree** (with NCIt cross-maps); tissues in
**UBERON**. Both are frozen snapshots in `vocab/` and membership-enforced.

## The curation trust gate

Every dataset carries a `curation_status`; a record climbs the tiers as evidence
accrues:

| Tier             | What it means                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `machine_draft`  | Auto-drafted from a source registry; nothing re-checked yet.                                                                                      |
| `human_reviewed` | A curator confirmed the accession resolves, the organism is human, and the platform is right.                                                     |
| `verified`       | The top tier: a live-resolving accession **plus** `last_verified` **plus** a linked `source_paper`. Enforced structurally by `build/validate.py`. |

A draft is a perfectly good contribution - the tier is honest, not a gate on
being merged.

## Local development

```bash
uv sync                                   # provision env from uv.lock
uv run python build/validate.py           # schema + trust gate + vocab (must pass)
uv run python build/compile.py            # build graph/tables/site payload
uv run python build/check_accessions.py --status verified   # pre-promotion link check
uv run --extra dev python -m pytest -q    # offline unit tests
uv run pre-commit install                 # optional: gate commits locally
```

CI runs the same validation + tests on every PR.

## Curator onboarding: taking an issue to a verified record

1. Read the "Add a dataset" issue and open the accession at its source; confirm
   the platform from the sample/methods text and the tissue.
2. Create `records/datasets/<platform>-<cancer>-<source>-<accession>.yaml` (see
   any existing record for the shape). Add a `records/papers/<slug>.yaml` node if
   the source paper is new. If the vocabulary lacks the tissue, add the CURIE to
   `vocab/uberon_tissue_seed.txt` and regenerate with `vocab/build_vocab.py`.
3. `uv run python build/validate.py` until green.
4. To ship `verified`: confirm the accession resolves and link the paper; set
   `last_verified`. Otherwise leave it `human_reviewed` / `machine_draft`.
5. Open a PR (the template has the checklist) referencing the issue.

Automated drafters exist to reduce transcription toil - `extract/draft_from_geo.py`
and the `build/harvest_*.py` harvesters propose `machine_draft` records - but a
human always makes the trust-tier call.

## Corrections and incidents

Found a wrong or dead record? Open an issue or, if you have access, use
`build/demote.py` and follow [`docs/INCIDENT_RESPONSE.md`](docs/INCIDENT_RESPONSE.md).

## Conventions

- Keep PRs small and focused; one study or one change per PR.
- Never invent an accession, paper, or platform. If a field is uncertain, use the
  lower trust tier and note the uncertainty in `reuse_notes`.
- Records are the source of truth; `build/dist/` and `_site/` are generated.

By contributing you agree that data records are released under CC-BY-4.0 and code
under MIT.
