import { useParams, Link } from "react-router-dom";
import { useSite } from "../data";
import type { Dataset as DatasetT } from "../types";
import {
  MODALITY_LABEL,
  accessionLink,
  accessionLabel,
  accessionParts,
  reuseBand,
} from "../lib/format";
import {
  AccessBadge,
  ModalityBadge,
  PlatformTag,
  StatusTag,
} from "../components/Badges";

function Accessions({ accession }: { accession: string }) {
  const parts = accessionParts(accession);
  return (
    <dd>
      {parts.map((acc, i) => {
        const href = accessionLink(acc);
        return (
          <span key={i}>
            {i > 0 && ", "}
            {href ? (
              <a
                className="acc"
                href={href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {accessionLabel(acc)}
              </a>
            ) : (
              <span>{acc}</span>
            )}
          </span>
        );
      })}
    </dd>
  );
}

function Paper({ d }: { d: DatasetT }) {
  if (d.paper_doi)
    return (
      <dd>
        <a
          className="acc"
          href={`https://doi.org/${d.paper_doi}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {d.paper_year ? String(d.paper_year) : "DOI"}
        </a>
      </dd>
    );
  return <dd>{String(d.paper_year || d.source_paper)}</dd>;
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  if (children === null || children === undefined || children === "")
    return null;
  return (
    <div className="d-row">
      <dt>{label}</dt>
      {typeof children === "string" || typeof children === "number" ? (
        <dd>{children}</dd>
      ) : (
        children
      )}
    </div>
  );
}

// `inModal` renders the record as a modal body: no <main>/back-link page
// chrome, since the catalog stays mounted behind the dialog.
export default function Dataset({ inModal = false }: { inModal?: boolean }) {
  const { id } = useParams();
  const { datasets } = useSite();
  const d = datasets.find((x) => x.id === id);

  if (!d) {
    const missing = (
      <p className="resultline">
        Dataset not found. <Link to="/catalog">Back to the catalog</Link>.
      </p>
    );
    return inModal ? (
      missing
    ) : (
      <main className="wrap detail-page">{missing}</main>
    );
  }

  const r = d.reusability;
  const val = (v: number | string) =>
    v === "" || v == null ? null : String(v);

  const content = (
    <>
      {!inModal && (
        <p className="detail-back">
          <Link to="/catalog" className="acc">
            &larr; Back to the catalog
          </Link>
        </p>
      )}

      <p className="modal-kicker">
        <ModalityBadge modality={d.modality} />
        <PlatformTag platform={d.platform} />
        <AccessBadge access={d.access} />
        <StatusTag status={d.curation_status} />
      </p>
      <h1 className="modal-cancer" id="dataset-title">
        {d.cancer_type_name || d.cancer_type}
      </h1>
      <p className="modal-sub">
        <span className="code">
          {d.cancer_type +
            (d.cancer_type_ncit ? "  ·  NCIt " + d.cancer_type_ncit : "")}
        </span>
      </p>
      <p className="modal-title-text">{d.title}</p>

      {r && (
        <div className="reuse-block">
          <div className="reuse-head">
            <span className={`reuse-pill reuse--${reuseBand(r.score)}`}>
              Reusability {r.score}%
            </span>
            <span className="reuse-frac">
              {r.met} of {r.total} signals
            </span>
          </div>
          <ul className="reuse-list">
            {r.signals.map((s) => (
              <li key={s.key} className={s.ok ? "ok" : "no"}>
                <span className="reuse-mark">{s.ok ? "✓" : "✗"}</span>
                <span>{s.label}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <dl className="detail">
        <Row label="Spatial platform">{val(d.platform)}</Row>
        <Row label="Sequencer">{val(d.sequencer)}</Row>
        <Row label="Modality">
          {val(MODALITY_LABEL[d.modality] || d.modality)}
        </Row>
        <Row label="Tissue">
          {d.tissue ? (
            <dd>
              {(d.tissue_label || "") + "  "}
              <span className="code">{d.tissue}</span>
            </dd>
          ) : null}
        </Row>
        <Row label="Samples">{val(d.n_samples)}</Row>
        <Row label="Patients">{val(d.n_patients)}</Row>
        <Row label="Access">{val(d.access)}</Row>
        <Row label="Curation">{val(d.curation_status)}</Row>
        <Row label="Last verified">{val(d.last_verified)}</Row>
        <Row label="Accession">
          {d.accession ? <Accessions accession={d.accession} /> : null}
        </Row>
        <Row label="Source paper">
          {d.source_paper ? <Paper d={d} /> : null}
        </Row>
        <Row label="Lab">{val(d.lab_name || d.lab)}</Row>
        <Row label="Method">{val(d.method_name || d.pipeline_ref)}</Row>
      </dl>

      {d.reuse_notes && (
        <div className="notes">
          <dt>Reuse notes</dt>
          <p>{d.reuse_notes}</p>
        </div>
      )}
    </>
  );

  return inModal ? (
    content
  ) : (
    <main className="wrap detail-page">{content}</main>
  );
}
