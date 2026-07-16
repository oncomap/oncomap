# vocab/ - frozen controlled vocabularies

Reproducible snapshots and mappings for the ontologies OncoMap adopts (never
mints). See `docs/OncoMap-SPEC.md §3`.

| Field              | Standard      | Snapshot file        | Status                   |
| ------------------ | ------------- | -------------------- | ------------------------ |
| `cancer_type`      | OncoTree      | `oncotree.json`      | ✅ frozen + enforced     |
| `cancer_type_ncit` | NCI Thesaurus | (in `oncotree.json`) | ✅ cross-map enforced    |
| `tissue`           | UBERON        | `uberon.json`        | ✅ frozen + enforced     |
| `platform` / assay | EFO / OBI     | (schema enum)        | 🟡 enum only (see below) |

## Regenerating snapshots

```bash
uv run --extra dev python vocab/build_vocab.py          # refresh all snapshots
uv run --extra dev python vocab/build_vocab.py --check  # assert snapshots present
```

`build_vocab.py` freezes each snapshot with its source **version** (where the
source exposes one) and **retrieval date**, so records stay reproducible against
a pinned vocabulary.

- **`oncotree.json`** - 897 codes + each code's NCIt cross-reference, fetched
  from the OncoTree API (pinned to `oncotree_latest_stable`).
- **`uberon.json`** - tissue terms curated in `uberon_tissue_seed.txt`; labels
  are fetched and validated against the EBI OLS4 API (a seed CURIE that OLS
  can't resolve fails the build). Add a term to the seed file when a real
  dataset needs a tissue not yet listed, then regenerate.

**Enforced by `build/validate.py` (Layer 4):**

- `dataset.cancer_type` must be a member of the frozen OncoTree code set.
- `dataset.cancer_type_ncit`, if given, must match the code's OncoTree→NCIt map.
- `dataset.tissue` must be a term in the frozen UBERON subset.

**Not yet frozen - `platform` / assay (EFO/OBI).** The `platform` field is a
closed 8-value enum in `schema/dataset.schema.json`, which already acts as a
controlled list. Mapping each platform to a confirmed EFO/OBI assay term (for
external interoperability) is deferred
rather than guessed, since minting an unverified ontology ID would defeat the
purpose.
