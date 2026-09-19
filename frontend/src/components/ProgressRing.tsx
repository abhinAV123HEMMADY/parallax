const R = 18;
const C = 2 * Math.PI * R;

export default function ProgressRing({
  value,
  total,
  label,
}: {
  value: number;
  total: number;
  label?: string;
}) {
  const pct = total === 0 ? 0 : Math.min(1, Math.max(0, value / total));
  return (
    <span className="ring" role="img" aria-label={label ?? `${value} of ${total} complete`}>
      <svg viewBox="0 0 42 42">
        <circle className="ring-track" cx="21" cy="21" r={R} />
        <circle
          className="ring-fill"
          cx="21"
          cy="21"
          r={R}
          strokeDasharray={C}
          strokeDashoffset={C * (1 - pct)}
        />
      </svg>
      <b>{label ?? `${value}/${total}`}</b>
    </span>
  );
}
