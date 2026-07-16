# OncoMap - Data Sources Registry

The sources OncoMap catalogs _from_ (and links _to_). OncoMap never re-hosts primary data - it records provenance and reuse metadata pointing at these sources. Scope: **human spatial transcriptomics of the tumor microenvironment** (Phase 1); expandable to single-cell and proteogenomics (Phase 4).

Legend - **Role:** `primary` = raw-data repository · `atlas` = curated consortium atlas · `aggregator` = harmonized multi-study platform · `spatial-DB` = spatial-specific curated database · `vocab` = ontology/standard · `vendor` = platform provider.

---

## 1. Primary data repositories (accession backbone)

| Source                                             | Role    | Access                  | Programmatic access      | Notes for OncoMap                                                         |
| -------------------------------------------------- | ------- | ----------------------- | ------------------------ | ------------------------------------------------------------------------- |
| **NCBI GEO**                                       | primary | Open                    | E-utilities / `GEOparse` | Dominant deposit target for ST series (`GSE…`). Primary accession field.  |
| **NCBI SRA**                                       | primary | Open / dbGaP-controlled | E-utilities, SRA Toolkit | Raw reads; often linked from GEO. Flag controlled-access as pointer only. |
| **EMBL-EBI BioStudies / ArrayExpress**             | primary | Open                    | REST API                 | European deposits; some 10x/Visium studies.                               |
| **Zenodo / figshare**                              | primary | Open                    | REST API, DOI            | Common for processed ST objects (`.h5ad`, images). Gives DOI provenance.  |
| **NCI Cancer Research Data Commons (CRDC / Gen3)** | primary | Open + controlled       | Gen3 / DRS manifests     | Federated cancer data commons; HTAN routes through here.                  |

## 2. Cancer atlases (consortium, high-value)

| Source                                 | Role  | Access            | Programmatic access                                                                                | Notes for OncoMap                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------- | ----- | ----------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Human Tumor Atlas Network (HTAN)**   | atlas | Open + controlled | **Public Data Portal metadata JSON** (no auth), Synapse, Google BigQuery (ISB-CGC), CRDC/Gen3, DRS | Flagship for tumor spatial + single-cell with standardized metadata. **Harvested** (`build/harvest_htan.py`) via the public Data Portal metadata (`processed_syn_data.json`) - no GCP/BigQuery/Synapse auth needed. Source of the spatial-proteomics cohorts (CODEX/CyCIF/MIBI/IMC/MxIF/mIHC/Orion/GeoMx), cataloged as `access: controlled` pointers. |
| **HuBMAP**                             | atlas | Open              | Data Portal API                                                                                    | Multi-modal spatial/single-cell of _healthy_ tissue - the normal-reference counterpart to HTAN.                                                                                                                                                                                                                                                        |
| **TCGA / GDC**                         | atlas | Open + controlled | GDC API                                                                                            | Bulk multi-omics baseline; not spatial, but the provenance anchor cancer researchers expect.                                                                                                                                                                                                                                                           |
| **CPTAC**                              | atlas | Open + controlled | CRDC / PDC API                                                                                     | Proteogenomics; relevant at Phase 4 expansion.                                                                                                                                                                                                                                                                                                         |
| **Human Cell Atlas (HCA) Data Portal** | atlas | Open              | DCP API                                                                                            | Broad single-cell reference; some spatial.                                                                                                                                                                                                                                                                                                             |

## 3. Harmonized aggregators (already-standardized)

| Source                             | Role       | Access                 | Programmatic access                                     | Notes for OncoMap                                                                                                                                                |
| ---------------------------------- | ---------- | ---------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CZ CELLxGENE Discover + Census** | aggregator | Open                   | **Census API (TileDB-SOMA), Python + R**; AWS Open Data | Largest standardized single-cell corpus; includes spatial modality; filter by disease/tissue. Best interoperability target - its schema informs OncoMap's vocab. |
| **Broad Single Cell Portal**       | aggregator | Open + some controlled | REST API                                                | Study-level single-cell + some spatial; good group/lab linkage.                                                                                                  |

## 4. Spatial-specific curated databases (the incumbents to differentiate from)

These already curate spatial datasets - but as **data/visualization/analysis** hubs. OncoMap's differentiation is the **cross-source provenance map** (dataset ↔ paper ↔ method ↔ group, with reuse annotations), cancer-scoped. Treat them as sources to cross-reference, not competitors to duplicate.

| Source                    | Role       | Scale (reported)                          | Notes                                                                             |
| ------------------------- | ---------- | ----------------------------------------- | --------------------------------------------------------------------------------- |
| **STOmicsDB** (CNGB)      | spatial-DB | 218 manually curated datasets, 17 species | One-stop hub w/ cell-type + region annotation. Cross-reference for coverage gaps. |
| **SODB** (Nature Methods) | spatial-DB | 100+ datasets, SOView viz                 | Interactive exploration; check for cancer subset.                                 |
| **CROST** (NAR 2024)      | spatial-DB | Comprehensive ST repository               | Newer; cross-check overlap.                                                       |
| **Aquila**                | spatial-DB | ~100 datasets                             | Supports user data submission + spatial community analysis.                       |
| **SpatialDB**             | spatial-DB | 24 datasets (2019, first-mover)           | Historical baseline; largely superseded.                                          |
| **SPASCER**               | spatial-DB | -                                         | Spatial single-cell atlas resource.                                               |

## 5. Platform / vendor dataset libraries

| Source                                                        | Role   | Access | Notes                                                                                             |
| ------------------------------------------------------------- | ------ | ------ | ------------------------------------------------------------------------------------------------- |
| **10x Genomics Datasets**                                     | vendor | Open   | Reference Visium / Visium HD / Xenium datasets, incl. cancer panels. Canonical platform metadata. |
| **Vizgen / NanoString (CosMx) / Bruker (MERSCOPE) showcases** | vendor | Open   | Platform demo datasets; useful for `platform` vocab calibration.                                  |

## 6. Controlled vocabularies & standards (adopt, never reinvent)

| Standard                   | Domain                                                                   | Use in OncoMap                                    |
| -------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------- |
| **OncoTree**               | Cancer type taxonomy (MSK)                                               | Primary `cancer_type` codes.                      |
| **NCI Thesaurus (NCIt)**   | Cancer terminology                                                       | Cross-map / disambiguation.                       |
| **UBERON**                 | Anatomy                                                                  | `tissue` field.                                   |
| **EFO / OBI**              | Experimental factors / assays                                            | `platform` / assay typing.                        |
| **HTAN metadata standard** | Tumor atlas metadata                                                     | Alignment target for interoperability with HTAN.  |
| **CELLxGENE schema**       | Single-cell metadata                                                     | Alignment target for aggregator interoperability. |
| **Persistent IDs**         | DOI, PMID, GEO/SRA accession, **ROR** (institutions), **ORCID** (people) | Edge keys linking datasets ↔ papers ↔ groups.     |

---

## 7. Source prioritization for Phase 1

1. **HTAN** - richest tumor spatial + standardized metadata; sets the schema bar.
2. **GEO + Zenodo** - where the long tail of individual-study spatial-TME datasets actually lives.
3. **CZ CELLxGENE Census** - interoperability anchor; harvest its disease/tissue facets.
4. **Cross-reference STOmicsDB / SODB / CROST** - to measure coverage and avoid missing known datasets.
5. **10x Genomics** - canonical `platform` metadata calibration.

## 8. Access & compliance notes

- **Open vs controlled:** only `access: open` datasets are cataloged with resolvable links. Controlled-access (dbGaP, some HTAN/TCGA) recorded as **pointers with access-mechanism noted**, never mirrored.
- **Rate limits:** NCBI E-utilities require an API key (≤10 req/s); Synapse/BigQuery require auth - store via secrets mechanism, never in records.
- **Licensing:** most sources are CC-BY or public-domain metadata; record each dataset's license in `reuse_notes`. OncoMap's own catalog ships **CC-BY-4.0 (data) / MIT (code)**.
