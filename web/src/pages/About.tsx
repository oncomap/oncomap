import { Link } from "react-router-dom";
import { useSite } from "../data";

const SOURCES = [
  ["GEO", "NCBI Gene Expression Omnibus - sequencing-based spatial series"],
  ["Zenodo", "Citable DOI deposits of primary spatial data"],
  ["HTAN", "Human Tumor Atlas Network portal (access-controlled pointers)"],
  ["BioImage Archive", "EBI S-BIAD imaging deposits - spatial proteomics"],
  ["CZ CELLxGENE", "Curated spatial collections"],
  ["ArrayExpress", "EBI BioStudies E-MTAB spatial studies"],
  ["10x Genomics", "Vendor reference datasets"],
];

const GITHUB = "https://github.com/oncomap/oncomap";

export default function About() {
  const { counts, facets } = useSite();
  return (
    <main className="wrap detail-page">
      <h1 className="page-title">About OncoMap</h1>

      <section className="band">
        <p className="prose">
          OncoMap is a curated, literature-grounded metadata catalog of oncology
          spatial-omics datasets - spatial transcriptomics and spatial
          proteomics - focused on the tumor microenvironment. It records
          provenance and reuse metadata pointing at public repositories; it
          never re-hosts primary data. The current snapshot covers{" "}
          <strong>{counts.datasets} datasets</strong> across{" "}
          <strong>{counts.cancer_types} cancer types</strong> and{" "}
          {facets.platform.length} platforms in {facets.modality.length}{" "}
          modalities.
        </p>
      </section>

      <section className="band">
        <h2 className="band-title">Curation trust gate</h2>
        <p className="prose">
          Every record is graded on a three-tier gate, so trust is explicit:
        </p>
        <ul className="tier-list">
          <li className="tier tier--verified">
            <span className="tier-name">verified</span>
            <span className="tier-desc">
              Human-reviewed, with a live-resolving accession, a last_verified
              date, and a linked source publication.
            </span>
          </li>
          <li className="tier tier--reviewed">
            <span className="tier-name">human_reviewed</span>
            <span className="tier-desc">
              A curator confirmed the accession resolves, the organism is human,
              and the platform is correct.
            </span>
          </li>
          <li className="tier tier--draft">
            <span className="tier-name">machine_draft</span>
            <span className="tier-desc">
              Auto-drafted from a source registry; accession and platform
              detected automatically, not yet human-reviewed.
            </span>
          </li>
        </ul>
      </section>

      <section className="band">
        <h2 className="band-title">Where the data comes from</h2>
        <p className="prose">
          Records are harvested and integrity-filtered from seven public
          sources, then coded in OncoTree (cancer types, with NCI Thesaurus
          cross-maps) and UBERON (tissues) from frozen, membership-enforced
          vocabulary snapshots:
        </p>
        <ul className="source-list">
          {SOURCES.map(([name, desc]) => (
            <li key={name}>
              <strong>{name}</strong> - {desc}
            </li>
          ))}
        </ul>
      </section>

      <section className="band">
        <h2 className="band-title">Reproducibility and citation</h2>
        <p className="prose">
          Human-editable YAML records are the source of truth; the browsable
          catalog and flat exports are compiled deterministically from them, and
          each release is a taggable, citable snapshot. Source, schema, and the
          full curation pipeline are on{" "}
          <a href={GITHUB} target="_blank" rel="noopener noreferrer" className="acc">
            GitHub
          </a>
          . Data records are released under CC-BY-4.0; the build tooling is
          MIT-licensed.
        </p>
        <p className="prose">
          <Link to="/catalog" className="acc">
            Explore the catalog &rarr;
          </Link>
        </p>
      </section>
    </main>
  );
}
