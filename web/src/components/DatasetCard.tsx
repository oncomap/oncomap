import { Link, useLocation } from "react-router-dom";
import type { Dataset } from "../types";
import { accessionLabel, accessionParts, reuseBand } from "../lib/format";
import { AccessBadge, ModalityBadge, PlatformTag, StatusTag } from "./Badges";

// The whole card is a <Link>, so accession/paper render as plain text here
// (nested <a> is invalid HTML). The resolvable outbound links live on the
// dataset detail page, which is not itself a link.
function AccessionValue({ accession }: { accession: string }) {
  const parts = accessionParts(accession);
  return <dd>{parts.map((acc) => accessionLabel(acc)).join(", ")}</dd>;
}

export default function DatasetCard({ d }: { d: Dataset }) {
  const score = d.reusability ? d.reusability.score : null;
  const location = useLocation();
  return (
    // `background` opens the record as a modal over the catalog; the same href
    // still resolves to the full page when opened directly or in a new tab.
    <Link
      to={`/dataset/${d.id}`}
      state={{ background: location }}
      className={`card card--${d.curation_status}`}
    >
      <div className="card-head">
        <h3 className="card-cancer">{d.cancer_type_name || d.cancer_type}</h3>
        <div className="card-badges">
          <ModalityBadge modality={d.modality} />
          <PlatformTag platform={d.platform} />
          <AccessBadge access={d.access} />
          <StatusTag status={d.curation_status} />
        </div>
      </div>
      <p className="card-sub">
        <span className="code">{d.cancer_type}</span>
        {d.tissue_label ? "  ·  " + d.tissue_label : ""}
      </p>
      <p className="card-title">{d.title}</p>
      <dl className="card-meta">
        <div>
          <dt>Accession</dt>
          <AccessionValue accession={d.accession} />
        </div>
        {d.n_samples !== "" && (
          <div>
            <dt>Samples</dt>
            <dd>{String(d.n_samples)}</dd>
          </div>
        )}
        {d.n_patients !== "" && (
          <div>
            <dt>Patients</dt>
            <dd>{String(d.n_patients)}</dd>
          </div>
        )}
        {d.source_paper && (
          <div>
            <dt>Paper</dt>
            <dd>{String(d.paper_year || d.paper_doi || d.source_paper)}</dd>
          </div>
        )}
      </dl>
      <div className="card-foot">
        {score !== null && (
          <span className={`reuse-pill reuse--${reuseBand(score)}`}>
            Reusability {score}%
          </span>
        )}
        <span className="card-open">Details &rarr;</span>
      </div>
    </Link>
  );
}
