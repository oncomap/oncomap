#!/usr/bin/env python3
"""Fetch and freeze controlled-vocabulary snapshots.

Freezes two vocabularies that records validate against:

  * OncoTree  -> vocab/oncotree.json  (cancer_type codes + NCIt cross-map)
  * UBERON    -> vocab/uberon.json    (tissue terms curated in
                 vocab/uberon_tissue_seed.txt, labels fetched from EBI OLS4)

Snapshots are committed to the repo so records validate against a fixed
vocabulary; this script exists to regenerate them reproducibly, NOT to run in
CI. Each snapshot records its source version / retrieval date so records stay
reproducible against a pinned vocabulary (SPEC §3).

Usage:
    python vocab/build_vocab.py            # refresh all snapshots
    python vocab/build_vocab.py --check    # assert snapshots exist, don't fetch
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi

    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:  # fall back to system trust store
    _SSL_CTX = None

VOCAB_DIR = Path(__file__).resolve().parent

ONCOTREE_VERSION = "oncotree_latest_stable"
ONCOTREE_URL = f"https://oncotree.mskcc.org/api/tumorTypes?version={ONCOTREE_VERSION}"
ONCOTREE_VERSIONS_URL = "https://oncotree.mskcc.org/api/versions"

OLS4_BASE = "https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms"
UBERON_SEED = VOCAB_DIR / "uberon_tissue_seed.txt"

# filename -> (label for messages)
SNAPSHOTS = {"oncotree.json": "OncoTree", "uberon.json": "UBERON"}


def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(
        req, timeout=60, context=_SSL_CTX
    ) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _write(filename: str, snapshot: dict) -> Path:
    out = VOCAB_DIR / filename
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    return out


# --------------------------------------------------------------------------- #
# OncoTree
# --------------------------------------------------------------------------- #
def build_oncotree() -> dict:
    versions = _get_json(ONCOTREE_VERSIONS_URL)
    release_date = next(
        (
            v["release_date"]
            for v in versions
            if v["api_identifier"] == ONCOTREE_VERSION
        ),
        None,
    )
    tumor_types = _get_json(ONCOTREE_URL)

    codes: dict[str, dict] = {}
    for t in tumor_types:
        code = t.get("code")
        if not code:
            continue
        ncit = (t.get("externalReferences") or {}).get("NCI") or []
        codes[code] = {
            "name": t.get("name"),
            "main_type": t.get("mainType"),
            "tissue": t.get("tissue"),
            "ncit": ncit[0] if ncit else None,
        }

    return {
        "source": "OncoTree (MSKCC)",
        "version": ONCOTREE_VERSION,
        "release_date": release_date,
        "retrieved": _dt.date.today().isoformat(),
        "url": ONCOTREE_URL,
        "license": "https://oncotree.mskcc.org - cite Kundra et al. JCO CCI 2021",
        "code_count": len(codes),
        "codes": dict(sorted(codes.items())),
    }


# --------------------------------------------------------------------------- #
# UBERON (curated tissue subset, labels validated against OLS4)
# --------------------------------------------------------------------------- #
def _read_seed_curies() -> list[str]:
    curies: list[str] = []
    for line in UBERON_SEED.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line and line not in curies:  # dedup, preserve order
            curies.append(line)
    return curies


def _fetch_uberon_label(curie: str) -> str | None:
    url = f"{OLS4_BASE}?obo_id={urllib.parse.quote(curie)}"
    data = _get_json(url)
    terms = (data.get("_embedded") or {}).get("terms") or []
    for t in terms:
        if t.get("obo_id") == curie:
            return t.get("label")
    return None


def build_uberon() -> dict:
    terms: dict[str, dict] = {}
    unresolved: list[str] = []
    for curie in _read_seed_curies():
        label = _fetch_uberon_label(curie)
        if label is None:
            unresolved.append(curie)
            continue
        terms[curie] = {"label": label}

    if unresolved:
        # A seed CURIE that OLS can't resolve is a curation error - surface it
        # loudly rather than silently freezing a broken vocabulary.
        raise SystemExit(
            "UBERON seed contains unresolvable CURIE(s): " + ", ".join(unresolved)
        )

    return {
        "source": "UBERON via EBI OLS4",
        "url": OLS4_BASE,
        "retrieved": _dt.date.today().isoformat(),
        "seed": str(UBERON_SEED.relative_to(VOCAB_DIR.parent)),
        "term_count": len(terms),
        "terms": dict(sorted(terms.items())),
    }


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="verify snapshots exist, don't fetch"
    )
    args = ap.parse_args(argv)

    if args.check:
        missing = [f for f in SNAPSHOTS if not (VOCAB_DIR / f).exists()]
        if missing:
            print(
                f"MISSING: {', '.join(missing)} - run `python vocab/build_vocab.py`",
                file=sys.stderr,
            )
            return 1
        for f in SNAPSHOTS:
            snap = json.loads((VOCAB_DIR / f).read_text())
            n = snap.get("code_count") or snap.get("term_count")
            print(f"OK: {f} ({n} entries, retrieved {snap['retrieved']}).")
        return 0

    onco = build_oncotree()
    _write("oncotree.json", onco)
    print(
        f"Wrote vocab/oncotree.json - {onco['code_count']} codes "
        f"({onco['version']}, release {onco['release_date']})."
    )

    uberon = build_uberon()
    _write("uberon.json", uberon)
    print(f"Wrote vocab/uberon.json - {uberon['term_count']} tissue terms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
