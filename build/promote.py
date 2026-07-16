#!/usr/bin/env python3
"""Promote machine_draft datasets to verified by linking their publication.

The trust gate (build/validate.py) lets a dataset reach curation_status: verified
only when it has a resolvable accession, a last_verified date and a source_paper.
The harvesters leave records at machine_draft with the accession in place; this
supplies the other two, doing real per-record work rather than flipping a flag:

  1. confirm the accession still resolves live (check_accessions.check_one),
  2. find the linked publication at the source registry:
       GEO          -> esummary pubmedids -> PubMed
       ArrayExpress -> BioStudies study links -> PubMed / DOI
       Zenodo       -> record related-identifiers -> journal DOI -> Crossref
  3. create (deduplicated) Paper nodes and set source_paper + last_verified, then
     flip the dataset to verified.

A record with no discoverable publication is left at machine_draft untouched, so
promotion never fabricates a link. Dataset files are edited surgically (only the
trailing status line plus two inserted keys); Paper nodes are created or appended.

Usage:
  uv run python build/promote.py --dry-run
  uv run python build/promote.py --source geo
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import check_accessions as ca
import validate

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF = "https://api.crossref.org/works"
BIOSTUDIES = "https://www.ebi.ac.uk/biostudies/api/v1/studies"
ZENODO = "https://zenodo.org/api/records"
UA = {"User-Agent": "OncoMap-promote/1.0 (+https://oncomap.org)"}
ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "records" / "datasets"
PAPERS = ROOT / "records" / "papers"
TODAY = date.today().isoformat()


def _get(url: str, accept: str | None = None) -> dict:
    h = dict(UA)
    if accept:
        h["Accept"] = accept
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(
                req, timeout=45, context=_SSL
            ) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0 + attempt)
    return {}


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def q(t: str) -> str:
    return '"' + (t or "").replace('"', "").strip() + '"'


# ---- publication metadata -------------------------------------------------


def pubmed_meta(pmid: str) -> dict | None:
    d = _get(f"{EUTILS}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json").get(
        "result", {}
    )
    x = d.get(pmid)
    if not x or x.get("error"):
        return None
    doi = next(
        (a["value"] for a in x.get("articleids", []) if a["idtype"] == "doi"), ""
    )
    year = 0
    m = re.match(r"(\d{4})", x.get("pubdate", ""))
    if m:
        year = int(m.group(1))
    auth = x.get("sortfirstauthor", "") or (
        x.get("authors", [{}])[0].get("name", "") if x.get("authors") else ""
    )
    return {
        "pmid": pmid,
        "doi": doi,
        "title": (x.get("title") or "").rstrip("."),
        "year": year,
        "venue": x.get("fulljournalname") or x.get("source") or "",
        "author": auth.split()[0] if auth else "anon",
    }


def crossref_meta(doi: str) -> dict | None:
    d = _get(f"{CROSSREF}/{urllib.parse.quote(doi)}").get("message", {})
    if not d:
        return None
    title = (d.get("title") or [""])[0]
    if not title:
        return None
    year = 0
    for k in ("published-print", "published-online", "published", "issued"):
        parts = d.get(k, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    auth = ""
    if d.get("author"):
        auth = d["author"][0].get("family", "") or d["author"][0].get("name", "")
    return {
        "pmid": "",
        "doi": doi.lower(),
        "title": title,
        "year": year,
        "venue": (d.get("container-title") or [""])[0],
        "author": auth or "anon",
    }


def find_geo_pub(acc: str) -> dict | None:
    # resolve GSE -> uid -> pubmedids
    idl = (
        _get(f"{EUTILS}/esearch.fcgi?db=gds&term={acc}[ACCN]&retmode=json")
        .get("esearchresult", {})
        .get("idlist", [])
    )
    if not idl:
        return None, True
    rows = _get(f"{EUTILS}/esummary.fcgi?db=gds&id={idl[0]}&retmode=json").get(
        "result", {}
    )
    x = rows.get(idl[0], {})
    pmids = x.get("pubmedids") or []
    if not pmids:
        return None, True
    return pubmed_meta(str(pmids[0])), True  # curator-assigned link is authoritative


def find_ae_pub(acc: str) -> dict | None:
    d = _get(f"{BIOSTUDIES}/{acc}")
    # BioStudies nests links and subsections as arbitrarily grouped lists; walk
    # the whole structure defensively and pull any PubMed id or journal DOI.
    blob = json.dumps(d)
    m = re.search(r"pubmed[^\d]{0,10}(\d{6,9})", blob, re.I)
    if m:
        meta = pubmed_meta(m.group(1))
        if meta:
            return meta, True  # study-linked PubMed id
    # No free-text DOI scraping: a DOI in the study record may be a cited
    # methods/reference paper, not the source, and cannot be told apart reliably.
    return None, True


def find_zenodo_pub(acc: str) -> dict | None:
    m = re.search(r"zenodo\.(\d+)", acc)
    if not m:
        return None
    d = _get(f"{ZENODO}/{m.group(1)}")
    md = d.get("metadata", {})
    rels = md.get("related_identifiers", []) or []
    wanted = {
        "issupplementto",
        "isdocumentedby",
        "ispublishedin",
        "isidenticalto",
        "iscitedby",
        "references",
        "ispartof",
    }
    for r in rels:
        if r.get("scheme", "").lower() != "doi":
            continue
        ident = (r.get("identifier") or "").lower()
        if "zenodo" in ident:
            continue
        if r.get("relation", "").lower() in wanted:
            meta = crossref_meta(ident)
            if meta and meta.get("title") and meta.get("year"):
                return meta, True  # depositor-declared related publication
    # No free-text DOI scraping from the description: those DOIs are often cited
    # methods/reference papers, indistinguishable from the true source paper.
    return None, True


# ---- paper index ----------------------------------------------------------


class Papers:
    def __init__(self):
        self.by_pmid: dict[str, str] = {}
        self.by_doi: dict[str, str] = {}
        self.ids: set[str] = set()
        self.records: dict[str, dict] = (
            {}
        )  # id -> {meta..., datasets:set, existed:bool}
        for p, (_, data) in validate.load_records("papers").items():
            self.ids.add(p)
            self.records[p] = {
                "doi": data.get("doi", ""),
                "pmid": str(data.get("pmid", "")),
                "title": data.get("title", ""),
                "year": data.get("year", 0),
                "venue": data.get("venue", ""),
                "datasets": set(data.get("datasets", []) or []),
                "existed": True,
                "dirty": False,
            }
            if data.get("pmid"):
                self.by_pmid[str(data["pmid"])] = p
            if data.get("doi"):
                self.by_doi[data["doi"].lower()] = p

    def get_or_create(self, meta: dict, code: str) -> str:
        if meta.get("pmid") and meta["pmid"] in self.by_pmid:
            return self.by_pmid[meta["pmid"]]
        if meta.get("doi") and meta["doi"].lower() in self.by_doi:
            return self.by_doi[meta["doi"].lower()]
        base = f"{slugify(meta['author'])}-{meta['year'] or 'na'}-{code.lower()}"
        pid = base
        n = 2
        while pid in self.ids:
            pid = f"{base}-{n}"
            n += 1
        self.ids.add(pid)
        self.records[pid] = {
            "doi": meta.get("doi", ""),
            "pmid": meta.get("pmid", ""),
            "title": meta["title"],
            "year": meta["year"],
            "venue": meta.get("venue", ""),
            "datasets": set(),
            "existed": False,
            "dirty": True,
        }
        if meta.get("pmid"):
            self.by_pmid[meta["pmid"]] = pid
        if meta.get("doi"):
            self.by_doi[meta["doi"].lower()] = pid
        return pid

    def link(self, pid: str, rid: str):
        rec = self.records[pid]
        if rid not in rec["datasets"]:
            rec["datasets"].add(rid)
            rec["dirty"] = True

    def flush(self):
        for pid, r in self.records.items():
            if not r["dirty"]:
                continue
            lines = [f"id: {pid}"]
            if r["doi"]:
                lines.append(f"doi: {r['doi']}")
            if r["pmid"]:
                lines.append(f'pmid: "{r["pmid"]}"')
            lines.append(f"title: {q(r['title'])}")
            lines.append(f"year: {r['year']}")
            if r["venue"]:
                lines.append(f"venue: {q(r['venue'])}")
            lines.append("datasets:")
            lines += [f"  - {d}" for d in sorted(r["datasets"])]
            (PAPERS / f"{pid}.yaml").write_text("\n".join(lines) + "\n")


def promote_dataset_file(path: Path, pid: str) -> bool:
    text = path.read_text()
    if "\ncuration_status: machine_draft" not in text and not text.startswith(
        "curation_status: machine_draft"
    ):
        return False
    repl = f'source_paper: {pid}\nlast_verified: "{TODAY}"\ncuration_status: verified'
    new = re.sub(r"curation_status:\s*machine_draft\s*$", repl, text.rstrip()) + "\n"
    if new == text:
        return False
    path.write_text(new)
    return True


def source_of(acc: str) -> str:
    if acc.startswith("GSE"):
        return "geo"
    if acc.startswith("E-MTAB"):
        return "arrayexpress"
    if "zenodo." in acc:
        return "zenodo"
    return "other"


FINDERS = {"geo": find_geo_pub, "arrayexpress": find_ae_pub, "zenodo": find_zenodo_pub}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        choices=["geo", "arrayexpress", "zenodo"],
        help="limit to one source",
    )
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    papers = Papers()
    datasets = validate.load_records("datasets")
    promoted = no_pub = dead = 0
    todo = []
    for rid, (path, d) in sorted(datasets.items()):
        if d.get("curation_status") != "machine_draft":
            continue
        acc = (d.get("accession") or [""])[0]
        src = source_of(acc)
        if args.source and src != args.source:
            continue
        if src not in FINDERS:
            continue
        todo.append((rid, path, d, acc, src))

    for rid, path, d, acc, src in todo:
        alive, _ = ca.check_one(acc)
        time.sleep(0.15)
        if not alive:
            dead += 1
            print(f"  [dead] {rid}  {acc}")
            continue
        meta, _trusted = FINDERS[src](acc)
        time.sleep(0.2)
        if not meta or not meta.get("title") or not meta.get("year"):
            no_pub += 1
            print(f"  [no-pub] {rid}")
            continue
        pid = papers.get_or_create(meta, d.get("cancer_type", "na"))
        papers.link(pid, rid)
        promoted += 1
        tag = "dry" if args.dry_run else "+"
        print(f"  [{tag}] {rid}  ->  {pid}")
        if not args.dry_run:
            promote_dataset_file(path, pid)
        if args.limit and promoted >= args.limit:
            break

    if not args.dry_run:
        papers.flush()
    print(
        f"\nPromoted {promoted} to verified, {no_pub} left at machine_draft "
        f"(no linked pub), {dead} dead accession(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
