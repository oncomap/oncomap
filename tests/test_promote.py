"""Offline unit tests for the machine_draft -> verified promoter.

No network: exercises source routing, slugify, the deduplicated Paper index, and
the surgical dataset-status edit with synthetic inputs.
"""

import promote as p


# --- source routing --------------------------------------------------------
def test_source_of():
    assert p.source_of("GSE12345") == "geo"
    assert p.source_of("E-MTAB-1234") == "arrayexpress"
    assert p.source_of("10.5281/zenodo.999") == "zenodo"
    assert p.source_of("some-other-id") == "other"


# --- slugify ---------------------------------------------------------------
def test_slugify_normalises():
    assert p.slugify("O'Neill") == "o-neill"
    assert p.slugify("Muller") == "muller"
    assert p.slugify("van der Berg") == "van-der-berg"


# --- deduplicated Paper index ----------------------------------------------
def _meta(pmid="", doi="", author="zzztest", year=2099, title="T", venue="V"):
    return {
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "year": year,
        "venue": venue,
        "author": author,
    }


def test_paper_dedup_by_pmid_and_doi():
    papers = p.Papers()
    a = papers.get_or_create(_meta(pmid="99900001"), "GB")
    a2 = papers.get_or_create(_meta(pmid="99900001", title="different"), "GB")
    assert a == a2  # same pmid -> same node

    b = papers.get_or_create(_meta(doi="10.9999/zzztest.b"), "GB")
    b2 = papers.get_or_create(_meta(doi="10.9999/zzztest.b"), "GB")
    assert b == b2 and b != a  # same doi -> same node, distinct from a


def test_paper_slug_collision_gets_suffix():
    papers = p.Papers()
    a = papers.get_or_create(_meta(pmid="99900010", author="zzzuniq", year=2098), "GB")
    b = papers.get_or_create(_meta(pmid="99900011", author="zzzuniq", year=2098), "GB")
    assert a == "zzzuniq-2098-gb"
    assert b == "zzzuniq-2098-gb-2"  # same slug, different paper -> suffixed


# --- surgical status edit --------------------------------------------------
def test_promote_dataset_file_rewrites_trailing_status(tmp_path):
    f = tmp_path / "rec.yaml"
    f.write_text(
        "id: visium-gb-geo-gse1\n"
        "cancer_type: GB\n"
        "reuse_notes: >-\n  machine drafted\n"
        "curation_status: machine_draft\n"
    )
    assert p.promote_dataset_file(f, "someone-2025-gb") is True
    out = f.read_text()
    assert "curation_status: verified" in out
    assert "source_paper: someone-2025-gb" in out
    assert 'last_verified: "' in out
    assert "machine_draft" not in out


def test_promote_dataset_file_noop_when_not_draft(tmp_path):
    f = tmp_path / "rec.yaml"
    f.write_text("id: x\ncuration_status: verified\n")
    assert p.promote_dataset_file(f, "someone-2025-gb") is False
