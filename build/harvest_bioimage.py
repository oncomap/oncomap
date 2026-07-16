#!/usr/bin/env python3
"""Harvest human tumour spatial studies from the EBI BioImage Archive.

A source for imaging-based spatial PROTEOMICS. Imaging proteomics (CODEX, IMC,
MIBI, CyCIF, mIF, Orion) are microscopy images, deposited in image repositories
rather than the sequence archives GEO/ArrayExpress serve. The BioImage Archive
(S-BIAD accessions, hosted in EBI BioStudies) is the EBI home for exactly this
data, so it reaches deposits that HTAN and Zenodo miss.

This reuses the GEO harvester's platform detector, proteomics-context gate,
conservative disease classifier and model/methods exclude filter, so records are
drafted on the same integrity bar:

  - the study's Biosample Organism must be Homo sapiens (BioImage Archive keeps
    organism in a subsection, not a top-level attribute like ArrayExpress),
  - a spatial platform keyword must appear in the title/description, and a
    detected proteomics platform must also carry protein/imaging context,
  - a distinctive malignancy term must classify the cancer type, and
  - model-system / methods / benchmark studies are dropped.

Every record lands at curation_status machine_draft, pointing at the resolvable
S-BIAD accession, for later human promotion.

Usage:
  uv run python build/harvest_bioimage.py --dry-run
  uv run python build/harvest_bioimage.py --pages 3
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import deposition  # sibling; repository deposition-year resolver
import harvest_geo as g  # reuse EXCLUDE, CLASSIFY, detect_platform, confirm_platform, write_draft
import validate

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

SEARCH = "https://www.ebi.ac.uk/biostudies/api/v1/search"
STUDY = "https://www.ebi.ac.uk/biostudies/api/v1/studies"
COLLECTION = "BioImages"
UA = {"User-Agent": "OncoMap-bioimage-harvester/1.0 (+https://oncomap.org)"}
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "records" / "datasets"
THROTTLE = 0.15

# Require an explicit malignancy term. The BioStudies search is loose and the
# shared classifier keys on organ words that also appear in normal-tissue atlases
# (the BioImage Archive holds many); this gate drops those false positives.
MALIGNANT = re.compile(
    r"cancer|carcinoma|tumou?r|malignan|neoplas|sarcoma|lymphoma|melanoma|"
    r"leukemi|myeloma|glioma|glioblastoma|blastoma|adenocarcinoma|metasta",
    re.I,
)

# Imaging-proteomics-first: this source exists to reach the modality GEO/AE miss.
QUERIES = [
    "CODEX cancer",
    "CODEX tumour",
    "imaging mass cytometry cancer",
    "imaging mass cytometry tumour",
    "MIBI cancer",
    "CyCIF cancer",
    "multiplexed immunofluorescence cancer",
    "multiplexed immunofluorescence carcinoma",
    "multiplexed imaging tumour",
    "PhenoCycler cancer",
    "Orion tumour",
    "spatial proteomics carcinoma",
]


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                req, timeout=45, context=_SSL
            ) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0 + attempt)
    return {}


def existing_accessions() -> set[str]:
    have = set()
    for f in DATASETS.glob("*.yaml"):
        have |= set(re.findall(r"S-BIAD\d+", f.read_text()))
    return have


def search_biad(query: str, pages: int, page_size: int = 100) -> list[str]:
    accs: list[str] = []
    for page in range(1, pages + 1):
        qs = urllib.parse.urlencode(
            {
                "query": query,
                "collection": COLLECTION,
                "pageSize": page_size,
                "page": page,
            }
        )
        hits = _get(f"{SEARCH}?{qs}").get("hits", [])
        if not hits:
            break
        for h in hits:
            acc = h.get("accession", "")
            if acc.startswith("S-BIAD"):
                accs.append(acc)
        time.sleep(THROTTLE)
    return accs


def _walk_attrs(sec: dict, out: list[tuple[str, str]]) -> None:
    """Collect (name, value) attribute pairs from a section and all subsections."""
    for a in sec.get("attributes", []) or []:
        if a.get("name"):
            out.append((a["name"], a.get("value") or ""))
    for sub in sec.get("subsections", []) or []:
        if isinstance(sub, list):
            for s in sub:
                if isinstance(s, dict):
                    _walk_attrs(s, out)
        elif isinstance(sub, dict):
            _walk_attrs(sub, out)


def study_fields(acc: str) -> dict:
    """Return Title, Description and Organism for an S-BIAD study.

    Organism lives in a Biosample subsection in the BioImage Archive, so the
    whole section tree is walked rather than reading only top-level attributes.
    """
    d = _get(f"{STUDY}/{acc}")
    if not isinstance(d, dict):
        return {}
    pairs: list[tuple[str, str]] = []
    _walk_attrs(d.get("section", {}) or {}, pairs)
    fields: dict[str, str] = {}
    organisms: list[str] = []
    for name, value in pairs:
        low = name.lower()
        if low == "organism":
            organisms.append(value)
        elif low in ("title", "description") and name not in fields:
            fields[name] = value
    if not fields.get("Title") and d.get("title"):
        fields["Title"] = d["title"]
    fields["Organism"] = " ".join(organisms)
    # ReleaseDate is a top-level study attribute (not under section).
    top_attrs = {
        a.get("name", ""): a.get("value", "") for a in (d.get("attributes", []) or [])
    }
    fields["deposition_year"] = deposition.year_from_biostudies_attrs(top_attrs)
    return fields


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pages", type=int, default=3, help="search pages per query")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    oncotree = validate.load_oncotree()
    uberon = set(validate.load_uberon())
    have = existing_accessions()

    candidates: list[str] = []
    seen_acc: set[str] = set()
    for query in QUERIES:
        for acc in search_biad(query, args.pages):
            if acc not in seen_acc and acc not in have:
                seen_acc.add(acc)
                candidates.append(acc)
    print(f"  {len(candidates)} unique new S-BIAD candidate(s) to inspect")

    drafted = 0
    per_type: dict[str, int] = {}
    for acc in candidates:
        fields = study_fields(acc)
        time.sleep(THROTTLE)
        if "homo sapiens" not in (fields.get("Organism", "") or "").lower():
            continue
        title = (fields.get("Title") or "").strip()
        desc = (fields.get("Description") or "").strip()
        blob = f"{title} {desc}"
        if g.EXCLUDE.search(blob):
            continue
        if not MALIGNANT.search(blob):
            continue  # drop normal-tissue atlases/references
        plat = g.detect_platform(blob)
        if not plat or not g.confirm_platform(plat, blob):
            continue
        # Classify on the TITLE only: tumour studies name the cancer in the title,
        # whereas normal-tissue atlases merely mention a disease in the description.
        code = tissue = None
        for rx, c, t in g.CLASSIFY:
            if rx.search(title):
                code, tissue = c, t
                break
        if not code or code not in oncotree or tissue not in uberon:
            continue
        note = (
            "Machine-drafted by the BioImage Archive/BioStudies harvester. S-BIAD "
            "accession; study Biosample Organism is Homo sapiens. Platform "
            f"detected as {plat} and cancer_type classified as {code} from a "
            "distinctive disease term in the study title/description. Confirm the "
            "spatial-only sample count, tissue detail, histology and data licence, "
            "and link the source paper before promoting past machine_draft."
        )
        x = {
            "accession": acc,
            "title": title,
            "n_samples": None,
            "deposition_year": fields.get("deposition_year"),
        }
        rid = g.write_draft(code, tissue, plat, x, note, args.dry_run, source="biad")
        if rid:
            per_type[code] = per_type.get(code, 0) + 1
            drafted += 1
            if args.limit and drafted >= args.limit:
                break

    verb = "would draft" if args.dry_run else "drafted"
    print(f"\nBioImage Archive harvester {verb} {drafted} new record(s).")
    if per_type:
        print(
            "  by type: " + ", ".join(f"{k}+{v}" for k, v in sorted(per_type.items()))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
