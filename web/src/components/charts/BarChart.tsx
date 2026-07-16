// Horizontal labelled bar list for a category breakdown. Hand-rolled (CSS bars),
// no chart library. Rows are drawn widest-first; width is relative to the max.
export interface BarRow {
  label: string;
  count: number;
  color?: string;
  title?: string;
}

export default function BarChart({
  rows,
  total,
}: {
  rows: BarRow[];
  total?: number;
}) {
  const max = rows.reduce((m, r) => Math.max(m, r.count), 0) || 1;
  const denom = total || rows.reduce((s, r) => s + r.count, 0) || 1;
  return (
    <div className="barchart" role="list">
      {rows.map((r) => {
        const pct = Math.round((r.count / denom) * 100);
        return (
          <div className="barrow" role="listitem" key={r.label} title={r.title}>
            <span className="barrow-label">{r.label}</span>
            <span className="barrow-track">
              <span
                className="barrow-fill"
                style={{
                  width: `${(r.count / max) * 100}%`,
                  background: r.color || "var(--primary)",
                }}
              />
            </span>
            <span className="barrow-val">
              {r.count}
              <span className="barrow-pct"> {pct}%</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}
