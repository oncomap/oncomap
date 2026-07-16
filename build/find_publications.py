#!/usr/bin/env python3
"""Surface newly-published papers for reviewed-but-unlinked datasets.

For each dataset that has been reviewed but has no `source_paper` yet, search
Europe PMC for papers that cite its GEO accession. Prints candidates for a
curator to verify and link; once linked (and the accession resolves), the
record becomes eligible for `verified`.

It never auto-links: the accession search can false-positive (a paper may
mention an accession string it does not actually own), so a human confirms the
match by detail before adding the edge. This is the "promote when published"
half of the freshness sweep (companion to build/check_accessions.py).

Runs weekly in CI and locally. Exit 0 (informational); writes a summary table
to GITHUB_STEP_SUMMARY when run in Actions.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request

import runlog  # sibling; structured run logging
import validate  # sibling module; reuse record loaders

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except ModuleNotFoundError:
    _SSL = None

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = {
    "User-Agent": "OncoMap-pubfinder/1.0 (+https://github.com/oncomap/oncomap)"
}


def epmc_citations(accession: str) -> list[dict]:
    """Return papers whose full text cites the accession (Europe PMC).

    Retries once on a transient/non-JSON response; returns [] if it can't parse
    (better to miss a candidate this run than crash the sweep).
    """
    q = urllib.parse.urlencode(
        {"query": f'"{accession}"', "format": "json", "pageSize": "5"}
    )
    data = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(f"{EPMC}?{q}", headers=UA)
            with urllib.request.urlopen(
                req, timeout=45, context=_SSL
            ) as r:  # noqa: S310
                data = json.loads(r.read().decode("utf-8"))
            break
        except Exception as e:  # transient network / non-JSON body
            if attempt == 1:
                print(
                    f"  (warning: Europe PMC lookup failed for {accession}: {type(e).__name__})"
                )
                return []
            time.sleep(1.0)
    out = []
    for x in data.get("resultList", {}).get("result", []):
        if x.get("pmid") or x.get("doi"):
            out.append(
                {
                    "pmid": x.get("pmid", ""),
                    "doi": x.get("doi", ""),
                    "title": x.get("title", ""),
                    "journal": x.get("journalTitle", ""),
                    "year": x.get("pubYear", ""),
                }
            )
    return out


def main() -> int:
    datasets = validate.load_records("datasets")
    candidates: dict[str, tuple[str, list[dict]]] = {}
    checked = 0

    for rid, (_, d) in sorted(datasets.items()):
        if d.get("source_paper"):
            continue  # already linked (all verified records are)
        accs = [
            a for a in (d.get("accession") or []) if str(a).upper().startswith("GSE")
        ]
        if not accs:
            continue
        checked += 1
        hits = epmc_citations(accs[0])
        if hits:
            candidates[rid] = (accs[0], hits)
        time.sleep(1.0)  # be polite to Europe PMC (avoids transient throttling)

    print(f"Scanned {checked} reviewed, unlinked dataset(s).")
    if candidates:
        print(f"\n{len(candidates)} have candidate publication(s) to VERIFY and link:")
        for rid, (acc, hits) in candidates.items():
            print(f"\n  {rid}  ({acc}):")
            for h in hits:
                print(
                    f"    pmid={h['pmid'] or '-'} doi={h['doi'] or '-'} "
                    f"({h['year']}) {h['journal'][:24]} :: {h['title'][:60]}"
                )
        print(
            "\nVerify each by detail (author overlap, cancer type, dates) before linking."
        )
    else:
        print("No new candidate publications.")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(
                f"### Publication sweep\n\nScanned {checked} reviewed, unlinked datasets. "
            )
            if candidates:
                fh.write(
                    f"**{len(candidates)} have candidate papers to verify + link:**\n\n"
                )
                for rid, (acc, hits) in candidates.items():
                    refs = "; ".join(
                        f"{h['pmid'] or h['doi']} ({h['year']})" for h in hits
                    )
                    fh.write(f"- `{rid}` ({acc}): {refs}\n")
            else:
                fh.write("No new candidate publications.\n")

    runlog.log("find_publications", scanned=checked, candidates=len(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
