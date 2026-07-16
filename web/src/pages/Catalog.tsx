import { useSearchParams } from "react-router-dom";
import { useSite } from "../data";
import { matches, sortRows, pageWindow, type Filters } from "../lib/format";
import DatasetCard from "../components/DatasetCard";

const MODALITY_TABS: [string, string][] = [
  ["", "All"],
  ["spatial_transcriptomics", "Transcriptomics"],
  ["spatial_proteomics", "Proteomics"],
];

const SORT_OPTS: [string, string][] = [
  ["cancer_type_name", "Cancer type"],
  ["platform", "Platform"],
  ["tissue_label", "Tissue"],
  ["n_samples", "Samples"],
  ["title", "Title"],
];

// param key -> filter field label, plus the facet list key on site.json
const FILTER_SELECTS: { param: keyof Filters; label: string; facet: string }[] =
  [
    { param: "platform", label: "Platform", facet: "platform" },
    { param: "cancer", label: "Cancer type", facet: "cancer_type" },
    { param: "access", label: "Access", facet: "access" },
    { param: "status", label: "Curation", facet: "curation_status" },
  ];

export default function Catalog() {
  const { datasets, facets } = useSite();
  const [params, setParams] = useSearchParams();
  const get = (k: string, def = "") => params.get(k) ?? def;

  const filters: Filters = {
    modality: get("modality"),
    platform: get("platform"),
    cancer: get("cancer"),
    access: get("access"),
    status: get("status"),
    q: get("q"),
  };
  const sort = get("sort", "cancer_type_name");
  const perPage = Number(get("perPage", "10")) || 10;

  function update(next: Record<string, string>, resetPage = true) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (resetPage) p.delete("page");
    setParams(p);
  }

  const rows = sortRows(
    datasets.filter((d) => matches(d, filters)),
    sort,
  );
  const total = datasets.length;
  const totalPages = Math.max(1, Math.ceil(rows.length / perPage));
  const page = Math.min(Math.max(1, Number(get("page", "1")) || 1), totalPages);
  const start = (page - 1) * perPage;
  const pageRows = rows.slice(start, start + perPage);

  const facetOpts = (key: string): string[] =>
    (facets as Record<string, string[]>)[key] || [];

  return (
    <main className="wrap">
      <div
        className="modality-toggle"
        role="group"
        aria-label="Filter by modality"
      >
        {MODALITY_TABS.map(([val, label]) => (
          <button
            key={val || "all"}
            type="button"
            className={
              "mod-btn" + (filters.modality === val ? " is-active" : "")
            }
            onClick={() => update({ modality: val })}
          >
            {label}
          </button>
        ))}
      </div>

      <form className="controls" onSubmit={(e) => e.preventDefault()}>
        <div className="control control--search">
          <label htmlFor="q">Search</label>
          <input
            id="q"
            type="search"
            placeholder="title, cancer, tissue, accession..."
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
          />
        </div>
        {FILTER_SELECTS.map(({ param, label, facet }) => (
          <div className="control" key={param}>
            <label htmlFor={`f-${param}`}>{label}</label>
            <select
              id={`f-${param}`}
              value={filters[param]}
              onChange={(e) => update({ [param]: e.target.value })}
            >
              <option value="">All</option>
              {facetOpts(facet).map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>
        ))}
        <div className="control">
          <label htmlFor="f-sort">Sort by</label>
          <select
            id="f-sort"
            value={sort}
            onChange={(e) => update({ sort: e.target.value })}
          >
            {SORT_OPTS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="clear"
          onClick={() =>
            update({ platform: "", cancer: "", access: "", status: "", q: "" })
          }
        >
          Clear
        </button>
      </form>

      <p className="resultline">
        {rows.length
          ? `Showing ${start + 1}–${start + pageRows.length} of ${rows.length}` +
            (rows.length !== total ? ` (filtered from ${total})` : "")
          : `0 of ${total} datasets`}
      </p>

      {rows.length === 0 ? (
        <p className="empty">No datasets match these filters.</p>
      ) : (
        <div className="cards">
          {pageRows.map((d) => (
            <DatasetCard key={d.id} d={d} />
          ))}
        </div>
      )}

      {rows.length > 0 && (
        <div className="pagerbar">
          <div className="pager-perpage">
            <span>Show</span>
            <select
              aria-label="Results per page"
              value={String(perPage)}
              onChange={(e) => update({ perPage: e.target.value })}
            >
              {["10", "25", "50"].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>per page</span>
          </div>
          {totalPages > 1 && (
            <div className="pager">
              <button
                type="button"
                className={
                  "pager-link pager-nav" + (page === 1 ? " disabled" : "")
                }
                disabled={page === 1}
                onClick={() => update({ page: String(page - 1) }, false)}
              >
                &lsaquo; Prev
              </button>
              {pageWindow(totalPages, page).map((item, i) =>
                item === "gap" ? (
                  <span key={`gap${i}`} className="pager-gap">
                    &hellip;
                  </span>
                ) : (
                  <button
                    key={item}
                    type="button"
                    className="pager-link"
                    aria-current={item === page ? "page" : undefined}
                    onClick={() => update({ page: String(item) }, false)}
                  >
                    {item}
                  </button>
                ),
              )}
              <button
                type="button"
                className={
                  "pager-link pager-nav" +
                  (page === totalPages ? " disabled" : "")
                }
                disabled={page === totalPages}
                onClick={() => update({ page: String(page + 1) }, false)}
              >
                Next &rsaquo;
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
