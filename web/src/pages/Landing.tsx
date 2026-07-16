import { Link } from "react-router-dom";
import { useSite } from "../data";
import { MODALITY_LABEL, STATUS_DESC } from "../lib/format";
import { useHead } from "../lib/useHead";

const GITHUB = "https://github.com/oncomap/oncomap";

// Top cancer types by dataset count, for the browse-by chips.
function topCancerTypes(
  datasets: { cancer_type: string; cancer_type_name: string }[],
  n: number,
) {
  const counts = new Map<string, { name: string; count: number }>();
  for (const d of datasets) {
    const cur = counts.get(d.cancer_type) || {
      name: d.cancer_type_name || d.cancer_type,
      count: 0,
    };
    cur.count += 1;
    counts.set(d.cancer_type, cur);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, n)
    .map(([code, v]) => ({ code, ...v }));
}

const KEY_PLATFORMS = ["visium", "xenium", "cosmx", "imc", "codex", "mxif"];

const EXAMPLES: { title: string; sub: string; to: string }[] = [
  {
    title: "Breast cancer + IMC",
    sub: "Imaging mass cytometry of the breast TME",
    to: "/catalog?cancer=BRCA&platform=imc",
  },
  {
    title: "Colorectal + Visium",
    sub: "Spot-based spatial transcriptomics",
    to: "/catalog?cancer=COADREAD&platform=visium",
  },
  {
    title: "Verified datasets only",
    sub: "Curated, publication-linked records",
    to: "/catalog?status=verified",
  },
  {
    title: "Glioblastoma proteomics",
    sub: "Spatial protein imaging in GBM",
    to: "/catalog?cancer=GB&modality=spatial_proteomics",
  },
];

export default function Landing() {
  const { counts, facets, datasets, generated_at, version } = useSite();
  // Title stays "OncoMap" on every route (useHead's empty title falls back to
  // the bare site name); only the meta description is page-specific.
  useHead(
    "",
    "OncoMap is a curated, ontology-linked catalog of public spatial transcriptomics and proteomics datasets for cancer research — find what data exists for your cancer type, platform, and modality, and whether you can reuse it.",
  );
  const stats: [string, number][] = [
    ["Datasets", counts.datasets],
    ["Cancer types", counts.cancer_types],
    ["Platforms", facets.platform.length],
    ["Modalities", facets.modality.length],
  ];
  const cancers = topCancerTypes(datasets, 8);
  const platforms = KEY_PLATFORMS.filter((p) => facets.platform.includes(p));

  return (
    <main>
      <section className="hero">
        <div className="wrap">
          <h1 className="hero-title">
            The curated catalog of public spatial-omics data for oncology
          </h1>
          <p className="hero-sub">
            Find what public spatial transcriptomics and proteomics data exists
            for your cancer type, platform, and modality - and whether you can
            actually reuse it.
          </p>
          <dl className="hero-stats">
            {stats.map(([label, val]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{val.toLocaleString()}</dd>
              </div>
            ))}
          </dl>
          {generated_at && (
            <p className="hero-meta">
              Updated {generated_at}
              {version && ` · version ${version}`}
            </p>
          )}
          <div className="hero-cta">
            <Link to="/catalog" className="btn btn--primary">
              Explore the catalog &rarr;
            </Link>
            <Link to="/about" className="btn btn--ghost">
              How it&rsquo;s curated
            </Link>
            <a
              href={GITHUB}
              target="_blank"
              rel="noopener noreferrer"
              className="hero-gh"
              aria-label="GitHub repository"
            >
              <svg
                viewBox="0 0 24 24"
                width="26"
                height="26"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58 0-.29-.01-1.04-.02-2.05-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.33-1.76-1.33-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.62-5.48 5.92.43.37.81 1.1.81 2.22 0 1.6-.01 2.9-.01 3.29 0 .32.22.7.83.58A12.01 12.01 0 0 0 24 12.5C24 5.87 18.63.5 12 .5z" />
              </svg>
            </a>
          </div>
        </div>
      </section>

      <div className="wrap">
        <section className="band">
          <h2 className="band-title">What this is</h2>
          <p className="prose">
            OncoMap is a curated metadata catalog - not a data host. It is the
            navigation layer above the atlases: a versioned, ontology-linked map
            of <strong>datasets, papers, methods, and groups</strong> that
            answers, in seconds, &ldquo;what public spatial data exists for my
            cancer type, platform, and modality, and can I reuse it?&rdquo;
            Every record is coded in OncoTree and UBERON and graded by a
            three-tier curation trust gate, so you can tell verified, reusable
            data from an unreviewed draft before spending any time.
          </p>
        </section>

        <section className="band">
          <h2 className="band-title">Browse by</h2>
          <nav className="chip-group" aria-label="Browse by cancer type">
            {cancers.map((c) => (
              <Link
                key={c.code}
                to={`/catalog?cancer=${c.code}`}
                className="chip"
              >
                {c.name} <span className="chip-n">{c.count}</span>
              </Link>
            ))}
          </nav>
          <nav className="chip-group" aria-label="Browse by modality">
            {facets.modality.map((m) => (
              <Link
                key={m}
                to={`/catalog?modality=${m}`}
                className="chip chip--modality"
              >
                {MODALITY_LABEL[m] || m}
              </Link>
            ))}
          </nav>
          <nav className="chip-group" aria-label="Browse by platform">
            {platforms.map((p) => (
              <Link key={p} to={`/catalog?platform=${p}`} className="chip">
                {p}
              </Link>
            ))}
          </nav>
        </section>

        <section className="band">
          <h2 className="band-title">Example queries</h2>
          <div className="example-grid">
            {EXAMPLES.map((ex) => (
              <Link key={ex.to} to={ex.to} className="example-card">
                <span className="example-title">{ex.title}</span>
                <span className="example-sub">{ex.sub}</span>
                <span className="example-go">Open &rarr;</span>
              </Link>
            ))}
          </div>
        </section>

        <section className="band">
          <h2 className="band-title">How records are graded</h2>
          <p className="prose">
            Trust is explicit and tiered - the differentiator of this catalog.
            Filter to the tier you need:
          </p>
          <ul className="tier-list">
            <li className="tier tier--verified">
              <span className="tier-name">verified</span>
              <span className="tier-desc">{STATUS_DESC.verified}</span>
            </li>
            <li className="tier tier--reviewed">
              <span className="tier-name">human_reviewed</span>
              <span className="tier-desc">{STATUS_DESC.human_reviewed}</span>
            </li>
            <li className="tier tier--draft">
              <span className="tier-name">machine_draft</span>
              <span className="tier-desc">{STATUS_DESC.machine_draft}</span>
            </li>
          </ul>
          <p className="prose" style={{ marginTop: "10px" }}>
            <Link to="/catalog?status=verified" className="acc">
              Jump to verified datasets &rarr;
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
