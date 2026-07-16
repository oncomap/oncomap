# OncoMap

**A curated, literature-grounded metadata map of oncology omics datasets.**

<!-- After minting the v0.1 DOI (see docs/RELEASE.md), replace XXXXXXX below with
     the Zenodo record id in the badge, the DOI links, and the Cite section. -->

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC--BY--4.0-blue.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Code: MIT](https://img.shields.io/badge/Code-MIT-green.svg)](LICENSE)

OncoMap is the navigation layer _above_ the atlases - a versioned, ontology-linked knowledge graph connecting **datasets ↔ methods ↔ papers ↔ research groups**, so a researcher can answer in seconds: _"What public data exists for my cancer type, on my platform, and can I actually reuse it?"_

Scope: **spatial omics of the tumor microenvironment (TME)** - spatial transcriptomics (the Phase 1 beachhead) and spatial proteomics (Phase 4, now active). Extends to single-cell and proteogenomics later without a schema rewrite.

This is a **data/schema-first project**, not a UI project. The load-bearing artifact is the schema + curated records; the browsable view is a thin layer over compiled tables, and a real app is deferred until coverage justifies it.

## Documentation

| Doc                                                      | Purpose                                                                                                     |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| [`docs/OncoMap-SPEC.md`](docs/OncoMap-SPEC.md)           | Strategy, scope boundaries, data model (4 node types), curation workflow, roadmap                           |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)           | Registry of source repositories, atlases, aggregators, spatial DBs, and controlled vocabularies             |
| [`docs/SECURITY.md`](docs/SECURITY.md)                   | Data-classification policy, lightweight threat model, secrets procedure                          |
| [`docs/DEPLOY.md`](docs/DEPLOY.md)                       | Hosting the browsable view at www.oncomap.org via Netlify / Cloudflare Pages (free)           |
| [`docs/RELEASE.md`](docs/RELEASE.md)                     | Cutting a versioned release and minting the Zenodo DOI                                           |
| [`docs/INCIDENT_RESPONSE.md`](docs/INCIDENT_RESPONSE.md) | Data-incident runbook: severity, demotion, corrective-action register                            |

## Repository layout

```
oncomap/
├── records/     # one YAML per node - human-editable source of truth
│   ├── datasets/  papers/  methods/  groups/
├── schema/      # JSON Schema per node type (draft 2020-12)
├── vocab/       # frozen mappings to OncoTree, UBERON, NCIt, EFO (structure only)
├── build/       # validate.py (gate) + compile.py (graph/tables/site) + check_accessions.py
├── extract/     # draft_from_geo.py: proposes drafts to proposals/, never commits
├── site/        # static browsable view over site.json (hosted at www.oncomap.org)
├── docs/        # specification & build plan
└── README.md
```

## Build & validate

**Validate** records against the schemas, the curation trust gate (a `verified`
dataset needs a resolvable accession + `last_verified` + source paper),
cross-record referential integrity, and controlled-vocabulary membership. This
runs in CI on every PR (`.github/workflows/validate.yml`) and as a pre-commit
hook.

**Compile** the records into a graph, flat tables, and a site payload. The
compiler is deterministic and re-runnable (same records in, same bytes out).

**Check accessions** resolve at their source registry (GEO/SRA/BioProject via
NCBI E-utilities, DOIs via doi.org). This is the live half of the trust gate:
`validate.py` requires a `verified` record to HAVE an accession; this confirms
it still resolves. Network-dependent, so it runs on a weekly schedule
(`.github/workflows/freshness.yml`) and locally before promoting to `verified`.

**Find publications** for reviewed-but-unlinked records: searches Europe PMC for
papers now citing each accession and surfaces candidates for a curator to verify
and link (never auto-links; the accession search can false-positive). This is
the "promote when published" half of the weekly freshness sweep.

```bash
uv sync                                 # provisions the env from uv.lock
uv run python build/validate.py         # exits non-zero on any invalid record
uv run python build/compile.py          # writes build/dist/ (see below)
uv run --extra build python build/compile.py   # also emit datasets.parquet
uv run python build/check_accessions.py        # resolve every accession
uv run python build/check_accessions.py --status verified  # pre-promotion gate
uv run python build/find_publications.py       # candidate papers for unlinked records
uv run python build/monitor.py                 # coverage/freshness SLIs + SLO alert
uv run python build/demote.py <id> --reason "..."  # demote a bad record + log it
uv run --extra dev python -m pytest -q  # offline unit tests
uv run pre-commit install               # optional: gate commits locally
```

**Draft** a candidate record from a GEO series. The drafter fills what it can
extract reliably (title, accession, sample count, platform), leaves the
judgement calls (`cancer_type`, `tissue`) as curator TODOs, and classifies
blockers (unresolved accession, non-human, SuperSeries, ambiguous/unsupported
platform, bad DOI). It writes to `extract/proposals/` (git-ignored) for review;
it never writes to `records/`.

```bash
uv run python extract/draft_from_geo.py GSE268014
```

Compiler outputs (`build/dist/`, git-ignored - regenerated, not source):

| Artifact                            | Contents                                                                                                                                         |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `datasets.csv` / `datasets.parquet` | flat one-row-per-dataset table, with paper/lab/method and OncoTree/UBERON names resolved                                                         |
| `graph.json`                        | knowledge graph: nodes (dataset/paper/method/group) + typed edges (`described_in`, `produced_by`, `processed_with`, derived `collaborates_with`) |
| `site.json`                         | denormalized payload + facets for the static browsable view                                                                                      |
| `summary.json`                      | coverage stats (counts by platform / cancer type / status / access)                                                                              |

### Browsable view

`site/` is a dependency-free, client-side view (no backend) over `site.json`:
search and filter by cancer type x platform x access, with GEO/DOI accession
links. It is hosted free from this repo (Netlify or Cloudflare Pages) at
`oncomap.org`, rebuilt on every push to `main` via `scripts/build_site.sh`. See
[`docs/DEPLOY.md`](docs/DEPLOY.md).

```bash
uv run python build/compile.py         # produce build/dist/site.json
python3 -m http.server 8765            # then open http://localhost:8765/site/
```

## Contributing

New datasets and corrections are welcome - no YAML or git required: open the
[**Add a dataset**](../../issues/new?template=add-a-dataset.yml) issue form and a
curator turns it into a record. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
data model, the trust gate, and the curator workflow.

## Status

Phases 0-3 complete; Phase 4 (modality extension) underway - spatial proteomics
is now first-class. In place: four node schemas, the validation pipeline + CI
gate, frozen OncoTree + UBERON vocabularies with membership enforcement, a
data-classification/security policy, the deterministic build compiler,
multi-source coverage harvesters (GEO / ArrayExpress / CELLxGENE / Zenodo /
HTAN), the static browsable view with a modality toggle, the `machine_draft ->
human_reviewed -> verified` promoter with an offline test suite, structured run
logging, an SLO-gated coverage/freshness monitor with a link-rot alert, a
data-incident runbook, and the contribution model (issue form +
`CONTRIBUTING.md`). A [resource-paper draft](paper/oncomap-resource-paper.md) is
in `paper/`. Coverage is **247 spatial-TME datasets across 42 cancer types and
16 platforms** - 175 spatial transcriptomics + 72 spatial proteomics (CODEX,
CyCIF, MIBI, IMC, MxIF, mIHC, Orion, GeoMx), from GEO, Zenodo, HTAN and the
BioImage Archive. Work
still gated on external accounts: minting the Zenodo v0.1 DOI
([`docs/RELEASE.md`](docs/RELEASE.md)) and connecting the host for
www.oncomap.org ([`docs/DEPLOY.md`](docs/DEPLOY.md)).

## Cite

If you use OncoMap, please cite the archived release. Citation metadata lives in
[`CITATION.cff`](CITATION.cff) (GitHub renders a "Cite this repository" panel);
the DOI is minted per [`docs/RELEASE.md`](docs/RELEASE.md). Once minted, replace
`XXXXXXX` below with the Zenodo record id.

> Samuriwo, T. (2026). _OncoMap: a curated, literature-grounded catalog of
> oncology spatial-omics datasets_ (Version 0.1.0) [Data set]. Zenodo.
> https://doi.org/10.5281/zenodo.XXXXXXX

```bibtex
@dataset{oncomap,
  author    = {Samuriwo, Tendayi},
  title     = {OncoMap: a curated, literature-grounded catalog of oncology spatial-omics datasets},
  year      = {2026},
  version   = {0.1.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.XXXXXXX},
  url       = {https://doi.org/10.5281/zenodo.XXXXXXX}
}
```

## License

Data: CC-BY-4.0 · Code: MIT
