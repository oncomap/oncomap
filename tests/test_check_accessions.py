"""Offline unit tests for the accession resolver.

No network: exercises scheme classification and the check_one routing by
stubbing the network helpers. Guards the regression where a SYNAPSE: accession
had a classify() case but no check_one() branch, so it fell through to a bogus
https://SYNAPSE:... probe and every HTAN pointer read as dead; and where a
Zenodo DOI was resolved via doi.org (whose /doi/ landing route 404s for live
deposits) instead of the record API.
"""

import check_accessions as c


def test_classify_schemes():
    assert c.classify("GSE12345") == "geo"
    assert c.classify("SRP123456") == "sra"
    assert c.classify("PRJNA123456") == "bioproject"
    assert c.classify("SYNAPSE:syn24185191") == "synapse"
    assert c.classify("10.5281/zenodo.17626826") == "doi"


def test_synapse_routes_to_synapse_resolver(monkeypatch):
    seen = {}

    def fake_synapse(syn):
        seen["syn"] = syn
        return True

    def no_fallthrough(url):
        raise AssertionError(f"fell through to _http_alive with {url!r}")

    monkeypatch.setattr(c, "_synapse_alive", fake_synapse)
    monkeypatch.setattr(c, "_http_alive", no_fallthrough)

    alive, detail = c.check_one("SYNAPSE:syn24185191")
    assert alive and detail == "synapse"
    assert seen["syn"] == "syn24185191"  # scheme stripped, bare id passed through


def test_zenodo_doi_uses_record_api(monkeypatch):
    urls = []
    monkeypatch.setattr(c, "_http_alive", lambda url: urls.append(url) or True)
    alive, detail = c.check_one("10.5281/zenodo.17626826")
    assert alive and detail == "doi"
    assert urls == ["https://zenodo.org/api/records/17626826"]


def test_plain_doi_uses_doi_org(monkeypatch):
    urls = []
    monkeypatch.setattr(c, "_http_alive", lambda url: urls.append(url) or True)
    c.check_one("10.1038/s41586-020-2649-2")
    assert urls == ["https://doi.org/10.1038/s41586-020-2649-2"]
