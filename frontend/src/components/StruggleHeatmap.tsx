import { InfoIcon } from "./Icons";
import type { StruggleFeedItem } from "../types";

/** Tint by rank: the hottest topics read warm, the rest stay neutral. */
const HEAT = ["heat-1", "heat-2", "heat-3", "heat-3"];

export default function StruggleHeatmap({ items }: { items: StruggleFeedItem[] }) {
  const byTopic = new Map<string, number>();
  items.forEach((i) => byTopic.set(i.topic_name, (byTopic.get(i.topic_name) ?? 0) + 1));
  const topics = [...byTopic.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);

  return (
    <div className="card animate-in">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <h3 style={{ margin: 0 }}>Struggle Heatmap</h3>
        <span
          className="faint"
          title="Relative signal across your cohort — never absolute scores"
          style={{ cursor: "help" }}
        >
          <InfoIcon />
        </span>
      </div>

      {topics.length === 0 ? (
        <div className="empty" style={{ padding: "22px 8px" }}>
          <span className="emoji">🌱</span>
          No connections have shared a struggle signal yet.
        </div>
      ) : (
        <div className="stat-row" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
          {topics.map(([topic, count], i) => (
            <div key={topic} className={`stat-tile ${HEAT[i]}`}>
              <b>{count}</b>
              <span style={{ textTransform: "capitalize" }}>{topic}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
