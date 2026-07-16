export interface LegendItem {
  label: string;
  color: string;
}

export default function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="chart-legend">
      {items.map((it) => (
        <li key={it.label}>
          <span className="legend-swatch" style={{ background: it.color }} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}
