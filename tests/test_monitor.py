"""Offline tests for the health monitor and the demotion tool."""

import demote
import monitor


# --- SLI computation (invariants, not brittle counts) ----------------------
def test_compute_slis_shape_and_invariants():
    s = monitor.compute_slis()
    for key in (
        "datasets",
        "cancer_types",
        "platforms",
        "verified_fraction",
        "linked_fraction",
        "stale_verified",
        "recent_fraction",
        "by_status",
    ):
        assert key in s
    assert s["datasets"] == sum(s["by_status"].values())
    for frac in ("verified_fraction", "linked_fraction", "recent_fraction"):
        assert 0.0 <= s[frac] <= 1.0
    # no accession report passed -> no live-resolution fields
    assert "dead_accessions" not in s


# --- SLO evaluation (the alert logic) --------------------------------------
def test_evaluate_healthy():
    s = {"verified_fraction": 0.6, "stale_verified": 0}
    assert monitor.evaluate(s) == []


def test_evaluate_flags_low_verified_and_stale():
    s = {"verified_fraction": 0.10, "stale_verified": 3}
    breaches = monitor.evaluate(s)
    assert any("verified_fraction" in b for b in breaches)
    assert any("stale_verified" in b for b in breaches)


def test_evaluate_link_rot_alert():
    s = {"verified_fraction": 0.9, "stale_verified": 0, "dead_accessions": 2}
    breaches = monitor.evaluate(s)
    assert any("LINK ROT" in b for b in breaches)


def test_evaluate_dead_zero_is_healthy():
    s = {"verified_fraction": 0.9, "stale_verified": 0, "dead_accessions": 0}
    assert monitor.evaluate(s) == []


# --- demotion status surgery -----------------------------------------------
def test_demote_file_flips_status(tmp_path):
    f = tmp_path / "rec.yaml"
    f.write_text(
        "id: x\ncancer_type: GB\nsource_paper: a-2025-gb\n"
        'last_verified: "2026-07-10"\ncuration_status: verified\n'
    )
    prev = demote.demote_file(f, "human_reviewed")
    assert prev == "verified"
    assert "curation_status: human_reviewed" in f.read_text()


def test_demote_file_missing_status_returns_none(tmp_path):
    f = tmp_path / "rec.yaml"
    f.write_text("id: x\ncancer_type: GB\n")
    assert demote.demote_file(f, "human_reviewed") is None
