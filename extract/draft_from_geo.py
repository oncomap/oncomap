#!/usr/bin/env python3
"""Draft a machine_draft dataset record from a GEO series.

Proposes, never commits. Fetches a GEO series' metadata + design text, fills the
fields it can extract reliably (title, accession, sample count, platform, source
paper), and leaves the judgement calls (cancer_type -> OncoTree, tissue ->
UBERON) as explicit TODOs for a curator. The draft is written to
extract/proposals/ (git-ignored), NOT records/, so nothing enters the validated
catalog without human review.

It classifies blockers so a curator knows why a draft is not ready:
  - unresolved_accession : GEO returns no series for the accession
  - non_human            : organism is not Homo sapiens (out of Phase 1 scope)
  - superseries          : accession is a SuperSeries (pick a subseries first)
  - ambiguous_platform   : no, or conflicting, spatial-platform keyword
  - unsupported_platform : a real platform outside the schema enum (e.g. GeoMx)
  - bad_doi              : the linked paper's DOI does not resolve

The network layer is thin; the extraction logic (detect_platform,
accession_kind, build_draft, classify) is pure and unit-tested in tests/.

Usage: uv run python extract/draft_from_geo.py GSE268014
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

import yaml

PROPOSALS = Path(__file__).resolve().parent / "proposals"

# Ordered longest-first so "visium hd" wins over the "visium" substring.
# Maps a lowercase design-text keyword to a schema `platform` enum value, or to
# a sentinel for a real-but-unsupported platform.
PLATFORM_KEYWORDS: list[tuple[str, str]] = [
    ("visium hd", "visium_hd"),
    ("visiumhd", "visium_hd"),
    ("xenium", "xenium"),
    ("merscope", "merscope"),
    ("merfish", "merfish"),
    ("cosmx", "cosmx"),
    ("stereo-seq", "stereo_seq"),
    ("stereo-xcr", "stereo_seq"),
    ("slide-seq", "slide_seq"),
    ("slide-seqv2", "slide_seq"),
    ("geomx", "@geomx"),  # real platform, not in the schema enum
    ("digital spatial profiler", "@geomx"),
    ("visium", "visium"),
    ("spatial transcriptomics", "visium"),  # weakest fallback (ST-era / 10x ST)
]

SCHEMA_PLATFORMS = {
    "st_array",
    "visium",
    "visium_hd",
    "xenium",
    "merfish",
    "merscope",
    "cosmx",
    "slide_seq",
    "stereo_seq",
}


def detect_platform(text: str) -> tuple[str | None, str]:
    """Return (platform, reason). platform is a schema enum value or None.

    None means the caller must treat it as a blocker; the reason distinguishes
    ambiguous_platform (nothing / conflicting) from unsupported_platform.
    """
    t = (text or "").lower()
    found: list[str] = []
    for kw, plat in PLATFORM_KEYWORDS:
        if kw in t and plat not in found:
            found.append(plat)

    if not found:
        return None, "ambiguous_platform:no spatial-platform keyword found"

    # Visium HD is a refinement of Visium, not a conflict.
    core = {p for p in found if p != "visium"} or set(found)
    if core == {"visium_hd"} or (found and found[0] == "visium_hd"):
        return "visium_hd", "ok"

    unsupported = {p for p in core if p.startswith("@")}
    real = {p for p in core if not p.startswith("@")}

    if len(real) == 1 and not unsupported:
        return real.pop(), "ok"
    if not real and unsupported:
        name = next(iter(unsupported)).lstrip("@")
        return None, f"unsupported_platform:{name} is not in the schema enum"
    # more than one real platform, or a real+unsupported mix
    allp = sorted(p.lstrip("@") for p in (real | unsupported))
    return None, "ambiguous_platform:multiple platforms " + ", ".join(allp)


def accession_kind(acc: str) -> str:
    """Classify an accession string by format (no network)."""
    a = acc.strip().upper()
    if re.fullmatch(r"GSE\d+", a):
        return "geo"
    if re.fullmatch(r"SR[PRXS]\d+", a):
        return "sra"
    if re.fullmatch(r"PRJNA\d+", a):
        return "bioproject"
    if re.match(r"10\.\d{4,9}/", acc.strip()):
        return "doi"
    if acc.strip().lower().startswith("http"):
        return "url"
    return "unknown"


def build_draft(meta: dict) -> tuple[dict, list[str]]:
    """Build a draft record dict + a list of blocker codes from fetched meta.

    `meta` keys: accession, title, n_samples, taxon, is_superseries,
    design_text, pmid, doi, doi_ok (bool|None).
    Pure: does no I/O, so it is unit-testable with synthetic metadata.
    """
    acc = meta["accession"]
    blockers: list[str] = []

    if meta.get("unresolved"):
        blockers.append("unresolved_accession")
    taxon = (meta.get("taxon") or "").lower()
    if taxon and taxon != "homo sapiens":
        blockers.append(f"non_human:{meta['taxon']}")
    if meta.get("is_superseries"):
        blockers.append("superseries")

    platform, reason = detect_platform(meta.get("design_text", ""))
    if platform is None:
        blockers.append(reason)

    if meta.get("doi") and meta.get("doi_ok") is False:
        blockers.append(f"bad_doi:{meta['doi']}")

    slug = f"{platform or 'spatial'}-geo-{acc.lower()}"
    draft = {
        "id": slug,
        "title": meta.get("title", ""),
        "cancer_type": "",  # TODO curator: map to an OncoTree code
        "tissue": "",  # TODO curator: map to a UBERON term
        "modality": "spatial_transcriptomics",
        "platform": platform or "",
        "n_samples": meta.get("n_samples") or None,
        "accession": [acc],
        "access": "open",
        "reuse_notes": (
            f"AUTO-DRAFT by extract/draft_from_geo.py from {acc}; NOT reviewed. "
            f"Curator must set cancer_type (OncoTree) and tissue (UBERON), "
            f"confirm platform, and resolve blockers before moving to records/."
        ),
        "curation_status": "machine_draft",
    }
    if meta.get("pmid"):
        draft["source_paper_pmid"] = str(meta["pmid"])  # hint; curator makes the node
    return draft, blockers


# --------------------------------------------------------------------------- #
# Thin network layer (not unit-tested; exercised by the CLI).
# --------------------------------------------------------------------------- #
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UA = {"User-Agent": "OncoMap-extract/1.0 (+https://github.com/oncomap/oncomap)"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(  # noqa: S310
        urllib.request.Request(url, headers=UA), timeout=45, context=_SSL
    ) as resp:
        return resp.read()


def fetch_geo(acc: str) -> dict:
    """Fetch GEO series metadata + design text for one accession."""
    q = urllib.parse.urlencode(
        {"db": "gds", "term": f"{acc}[ACCN] AND gse[ETYP]", "retmode": "json"}
    )
    ids = (
        json.loads(_get(f"{EUTILS}/esearch.fcgi?{q}"))
        .get("esearchresult", {})
        .get("idlist", [])
    )
    if not ids:
        return {"accession": acc, "unresolved": True}
    s = urllib.parse.urlencode({"db": "gds", "id": ids[0], "retmode": "json"})
    rec = json.loads(_get(f"{EUTILS}/esummary.fcgi?{s}"))["result"][ids[0]]
    text = _get(
        f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=self&form=text&view=quick"
    ).decode("utf-8", "replace")
    design = " ".join(
        re.findall(r"!Series_(?:overall_design|summary|title) = (.*)", text)
    )
    return {
        "accession": acc,
        "unresolved": False,
        "title": rec.get("title", ""),
        "n_samples": rec.get("n_samples"),
        "taxon": rec.get("taxon", ""),
        "is_superseries": "SuperSeries" in text,
        "design_text": design,
        "pmid": (rec.get("pubmedids") or [None])[0],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("accession", help="GEO series accession, e.g. GSE268014")
    ap.add_argument("--out", help="output path (default extract/proposals/<id>.yaml)")
    args = ap.parse_args(argv)

    if accession_kind(args.accession) != "geo":
        print(
            f"error: {args.accession} is not a GEO series accession (GSE...)",
            file=sys.stderr,
        )
        return 2

    meta = fetch_geo(args.accession)
    draft, blockers = build_draft(meta)

    PROPOSALS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else PROPOSALS / f"{draft['id']}.yaml"
    out.write_text(
        yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=1000)
    )

    print(f"Proposed draft -> {out}")
    print(
        f"  platform: {draft['platform'] or '(unresolved)'} | title: {draft['title'][:70]}"
    )
    if blockers:
        print(f"  BLOCKERS ({len(blockers)}): curator must resolve before committing")
        for b in blockers:
            print(f"    - {b}")
    else:
        print("  no blockers; curator still sets cancer_type + tissue")
    print(
        "  This is a PROPOSAL in extract/proposals/ (git-ignored), not a committed record."
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
