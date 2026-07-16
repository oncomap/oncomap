# OncoMap - data incident response

A "data incident" is anything that makes a catalogued record wrong or
unreachable: an accession dies (link rot), a source repository restructures its
identifiers, a `verified` record turns out to be mislabelled, or licensing /
access status changes. Code incidents (CI, build) are ordinary engineering; this
runbook is about the **data**.

## How incidents surface

| Source                   | Signal                                                                                             |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| Weekly freshness sweep   | `check_accessions.py` reports a DEAD accession; `monitor.py` raises an SLO breach (link-rot alert) |
| Weekly publication sweep | `find_publications.py` surfaces a paper that contradicts a record's cancer type / platform         |
| External report          | A user or contributor flags a wrong record via an issue                                            |
| Curation review          | A reviewer spots a mislabel while promoting drafts                                                 |

## Severity

| Sev    | Definition                                                                                                          | Examples                                                                                  | Response time      |
| ------ | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------ |
| **S1** | A `verified` record is factually wrong (wrong cancer type, platform, or non-human) or advertises gated data as open | melanoma record that is actually basal cell carcinoma; `access: open` on restricted files | same day           |
| **S2** | A `verified` accession no longer resolves (link rot) but the record is otherwise correct                            | GSE returns 404; DOI unresolved                                                           | within the week    |
| **S3** | A lower-tier (`human_reviewed` / `machine_draft`) record is wrong, or a cosmetic/metadata issue                     | draft with an unconfirmed tissue                                                          | next curation pass |

## Response procedure

1. **Confirm** the defect at the source (open the GEO/ArrayExpress/Zenodo page;
   re-run `uv run python build/check_accessions.py --status verified`).
2. **Contain** - demote the record out of the trust tier it no longer merits and
   log the corrective action in one step:
   ```bash
   uv run python build/demote.py <record-id> --reason "GSE... 404s at GEO"        # link rot -> human_reviewed
   uv run python build/demote.py <record-id> --to machine_draft --reason "..."    # factual defect -> machine_draft
   ```
   For a wrong value (not just a dead link), also correct the field in the record
   before re-promoting.
3. **Verify** - `uv run python build/validate.py` stays green; the trust gate
   will now reject the record as `verified` until the defect is fixed and it is
   re-promoted with a resolving accession + `last_verified` + `source_paper`.
4. **Recover** - once fixed, re-run `check_accessions.py` and re-promote
   (`promote.py` / manual link) to restore `verified`.
5. **Communicate** - S1/S2 corrections are noted in the next release's notes and
   remain visible in the register below.

## Roles

Single-maintainer project today: the maintainer is detector, fixer, and
approver, but the **audit trail is the control** - every status change goes
through a commit (PR-reviewable) and the register, so the history is
reconstructable regardless of who acts.

## Corrective-action register

All demotions and material corrections are recorded in
[`CORRECTIVE_ACTIONS.md`](CORRECTIVE_ACTIONS.md); `demote.py` appends to it
automatically.
