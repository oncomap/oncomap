# OncoMap - corrective-action register

Append-only log of data corrections and demotions. `build/demote.py` adds a row
automatically; material corrections made without a demotion are added by hand.
See [`INCIDENT_RESPONSE.md`](INCIDENT_RESPONSE.md) for the procedure and severity
levels. Newest entries at the bottom.

| Date       | Record(s)                  | Action                         | Reason                                                                                                                                                                                                             |
| ---------- | -------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-07-09 | `xenium-bcc-geo-gse291246` | relabel SKCM -> BCC            | Verified record was mislabelled as melanoma; the GEO series design specifies basal cell carcinoma (S1 factual defect, caught in curation review).                                                                  |
| 2026-07-10 | 17 Zenodo records          | `access: open` -> `on_request` | Deposits whose Zenodo metadata is public but whose files are restricted/embargoed were advertised as openly downloadable, breaching the data-classification policy (S1). Harvester patched to read `access_right`. |
