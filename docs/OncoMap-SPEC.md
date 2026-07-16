# OncoMap

**A curated, literature-grounded metadata map of oncology omics datasets.**

OncoMap is not another data atlas. It is the navigation layer _above_ the atlases - a versioned, ontology-linked knowledge graph that connects **datasets ↔ methods ↔ papers ↔ research groups**, so a researcher can answer in seconds: _"What public data exists for my cancer type, on my platform, and can I actually reuse it?"_

Scope: **spatial omics of the tumor microenvironment (TME)** - spatial transcriptomics and spatial proteomics, the fastest-moving oncology-omics area with no unified metadata standard. The schema is designed to extend to single-cell and proteogenomics later.

---

## 1. Why this exists

The raw-data layer is saturated and well-funded: TCGA, CPTAC, Human Tumor Atlas Network, Human Cell Atlas, CZI CellxGene, DepMap. Producing another dataset adds nothing.

What omics researchers actually lose time to is the layer _nobody owns_: discovering which dataset covers a given `cancer type × platform × modality`, whether it is reusable, what pipeline produced it, and which paper and lab it came from. OncoMap fills exactly that gap.

**Design principles**

- **Narrow before broad.** One area done well (spatial-TME) beats all-of-oncology done thinly.
- **Metadata, not data.** We link to accessions; we never re-host primary data.
- **Human-gated, machine-drafted.** LLM-assisted extraction proposes entries; a curator approves. Trust is the product.
- **Citable and versioned.** Every release is taggable and reproducible - this is what makes it a resource paper, not a link dump.

---

## 2. Scope boundaries

**In scope**

- Public spatial omics datasets of human cancer tissue: spatial transcriptomics (Visium, Visium HD, Xenium, MERFISH/MERSCOPE, CosMx, Slide-seq, Stereo-seq) and spatial proteomics (CODEX, CyCIF, MxIF, mIHC, MIBI, IMC, Orion, GeoMx).
- Each dataset's provenance: source publication, generating lab, processing pipeline, accession.

**Out of scope (explicitly, to prevent drift)**

- Re-hosting or re-processing raw data.
- Non-human / model-organism spatial data.
- Full-text mining of _all_ oncology literature - we extract structured metadata for cataloged datasets only, not a general NLP engine.
- Clinical/patient-identifiable data.

**Expansion path:** the same schema extends to single-cell multi-omics and proteogenomics by adding `Modality` values and platform vocab - no schema rewrite.

---

## 3. Data model

Four core node types and the edges between them. Stored as human-editable YAML/JSON per record, compiled into a graph + flat tables + an API.

### Node: `Dataset`

| Field             | Type          | Notes                                                                        |
| ----------------- | ------------- | ---------------------------------------------------------------------------- |
| `id`              | string (slug) | Stable primary key, e.g. `visium-brca-10x-2023-001`                          |
| `title`           | string        | Human-readable name                                                          |
| `cancer_type`     | enum          | Mapped to NCIt / OncoTree code                                               |
| `tissue`          | enum          | Mapped to UBERON                                                             |
| `modality`        | enum          | `spatial_transcriptomics` / `spatial_proteomics` |
| `platform`        | enum          | Visium / Xenium / MERFISH / CosMx / …                                        |
| `n_samples`       | int           | Sample/section count                                                         |
| `n_patients`      | int           | If reported                                                                  |
| `accession`       | string[]      | GEO / SRA / Zenodo / HTAN IDs                                                |
| `access`          | enum          | `open` / `controlled` / `on_request`                                         |
| `reuse_notes`     | string        | Format quirks, missing metadata, license caveats                             |
| `pipeline_ref`    | id            | → `Method` node                                                              |
| `source_paper`    | id            | → `Paper` node                                                               |
| `lab`             | id            | → `Group` node                                                               |
| `curation_status` | enum          | `machine_draft` / `human_reviewed` / `verified`                              |
| `last_verified`   | date          | Provenance freshness                                                         |

### Node: `Paper`

`id`, `doi`, `pmid`, `title`, `year`, `venue`, `datasets[]`

### Node: `Method`

`id`, `name`, `type` (assay / pipeline / model), `version`, `repo_url`, `reference_paper`

### Node: `Group`

`id`, `name` (lab/PI), `institution`, `country`, `focus_areas[]`, `datasets[]`, `orcid`/`ror`

> The research-group directory you originally considered building falls out here for free - as one node type, kept fresh by its edges to datasets rather than manually maintained.

### Edges

`Dataset -produced_by→ Group`, `Dataset -described_in→ Paper`, `Dataset -processed_with→ Method`, `Group -collaborates_with→ Group` (derived from co-authorship).

### Controlled vocabularies (adopt, don't invent)

- Cancer type: **OncoTree** + **NCIt**
- Anatomy: **UBERON**
- Assay: **EFO** / **OBI** where available
- Persistent IDs: **DOI, PMID, GEO/SRA accession, ROR (institutions), ORCID (people)**

Using existing ontologies is what makes OncoMap interoperable and gives it a credible path to a Nucleic Acids Research database paper.

---

## 4. Repository layout

```
oncomap/
├── records/                # one YAML per dataset - the human-editable source of truth
│   ├── datasets/
│   ├── papers/
│   ├── methods/
│   └── groups/
├── schema/                 # JSON Schema for each node type + CI validation
├── vocab/                  # frozen snapshots / mappings to OncoTree, UBERON, NCIt
├── build/                  # scripts: records → graph, tables (CSV/Parquet), API payload
├── extract/                # LLM-assisted draft-entry tooling (proposes, never commits)
├── site/                   # static browsable table + search (GitHub Pages)
├── CONTRIBUTING.md
└── README.md
```

---

## 5. Curation workflow (trust gate)

1. **Draft** - `extract/` proposes a `machine_draft` record from a paper's methods/data-availability section.
2. **Review** - a human curator checks accession validity, platform, sample counts, license → `human_reviewed`.
3. **Verify** - a second pass confirms the accession actually resolves and is reusable → `verified` + `last_verified` date.
4. **CI gate** - schema validation, vocab-term validation, and dead-accession checks run on every PR. Nothing merges as `verified` without a resolvable accession.

This is the single most important part: the value of OncoMap over a scraped list is that every `verified` entry has been eyeballed.

---

## 6. Roadmap

The catalog grows in stages: lock the schema and seed hand-curated records; expand coverage and publish versioned, DOI-minted releases; open a contribution workflow for external curators; then extend to further modalities. The schema is designed so new modalities need only new `modality`/`platform` vocabulary, not a rewrite.

---

## 7. What would make this fail (and the guardrails)

- **Scope creep into all-of-oncology** → hard scope boundary in §2; new modalities only via an explicit scope decision.
- **Machine-drafted junk erodes trust** → nothing ships `verified` without human review + resolvable accession (§5).
- **Metadata rot** → `last_verified` field + CI dead-link checks make staleness visible and fixable.
- **Reinventing ontologies** → adopt OncoTree/UBERON/NCIt; never mint local terms when a standard exists.
- **Solo-maintainer burnout** → metadata is cheap and chunkable; the contribution model (§6) distributes load early.

---

## 8. Success metrics

- **Coverage:** % of spatial-TME datasets from the last 24 months that are cataloged.
- **Trust:** % of records at `verified` status; accession resolve-rate.
- **Adoption:** unique repo/API consumers; external citations of the resource DOI.
- **Community:** number of external contributors and curators.

---

_Beachhead: spatial omics of the TME (transcriptomics + proteomics). Long game: the metadata map the whole omics-oncology field navigates by._
