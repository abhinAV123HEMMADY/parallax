import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMasteryGraph } from "../api/rest";
import ExamPlanner from "../components/ExamPlanner";
import MasteryGraph from "../components/MasteryGraph";
import { ArrowIcon, CloseIcon } from "../components/Icons";
import { useLearner } from "../LearnerContext";
import type { MasteryGraph as Graph, MasteryNode, MasteryStatus } from "../types";

const STATUS_META: Record<MasteryStatus, { label: string; tag: string }> = {
  mastered: { label: "Solid", tag: "on_track" },
  decaying: { label: "Fading from memory", tag: "struggling" },
  gap: { label: "Blocking gap", tag: "struggling" },
  weak: { label: "Needs work", tag: "struggling" },
  untouched: { label: "Not started", tag: "neutral" },
};

function NodeSheet({
  node,
  graph,
  onClose,
  onLearn,
}: {
  node: MasteryNode;
  graph: Graph;
  onClose: () => void;
  onLearn: () => void;
}) {
  const meta = STATUS_META[node.status];
  const blocks = graph.edges.filter((e) => e.from === node.id).map((e) => e.to);
  const decayPct = node.retrievability === null ? null : Math.round(node.retrievability * 100);

  return (
    <div className="scrim" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <span className="eyebrow">{node.subject}</span>
            <h3 style={{ margin: "4px 0 0", textTransform: "capitalize" }}>{node.name}</h3>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>

        <span className={`tag ${meta.tag}`}>{meta.label}</span>

        <div className="stat-row" style={{ gridTemplateColumns: "repeat(3,1fr)", marginTop: 14 }}>
          <div className="stat-tile">
            <b>{Math.round(node.mastery * 100)}%</b>
            <span>PEAK MASTERY</span>
          </div>
          <div className="stat-tile">
            <b>{decayPct === null ? "—" : `${decayPct}%`}</b>
            <span>RETAINED NOW</span>
          </div>
          <div className="stat-tile">
            <b>{node.cards_tracked}</b>
            <span>CARDS</span>
          </div>
        </div>

        <div className="meter" style={{ marginTop: 14 }}>
          <span style={{ width: `${Math.max(4, node.effective_mastery * 100)}%` }} />
        </div>

        <p className="muted" style={{ marginTop: 14 }}>
          {node.status === "gap" || node.status === "weak"
            ? blocks.length
              ? `This is an unmet prerequisite — it's blocking ${blocks.join(", ")} downstream. Master it first.`
              : "Your effective mastery here is below threshold. Worth a focused pass."
            : node.status === "decaying"
              ? "You knew this well, but it's decaying. A quick review restores it before you forget."
              : node.status === "untouched"
                ? "You haven't started this node yet — it's next in the chain."
                : "Strong and well-retained. Nothing to do here right now."}
        </p>

        {node.status !== "mastered" && (
          <button className="block" style={{ marginTop: 6 }} onClick={onLearn}>
            {node.status === "decaying" ? "Review now" : "Learn this"} <ArrowIcon size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

export default function MasteryMap() {
  const { learnerId } = useLearner();
  const navigate = useNavigate();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setGraph(null);
    setError(false);
    setSelected(null);
    getMasteryGraph(learnerId)
      .then(setGraph)
      .catch(() => setError(true));
  }, [learnerId]);

  const selectedNode = useMemo(
    () => graph?.nodes.find((n) => n.id === selected) ?? null,
    [graph, selected],
  );

  return (
    <div>
      <div className="page-title">
        <h1>Your knowledge, alive</h1>
        <p>
          Every concept you've touched, sized by how much you retain <em>right now</em>. Nodes fade
          as memory decays — tap one to see what's slipping.
        </p>
      </div>

      {error ? (
        <div className="callout warn animate-in">
          <span className="eyebrow">Couldn't load mastery data</span>
          <p style={{ margin: "6px 0 0" }}>
            Make sure the backend is running, then reload this page.
          </p>
        </div>
      ) : !graph ? (
        <div className="graph-wrap" style={{ padding: 18 }}>
          <div className="skeleton" style={{ height: 380 }} />
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 12 }}>
            <div className="stat-row">
              <div className="stat-tile">
                <b>{Math.round(graph.summary.overall * 100)}%</b>
                <span>OVERALL</span>
              </div>
              <div className="stat-tile">
                <b style={{ color: "var(--ontrack)" }}>{graph.summary.mastered}</b>
                <span>SOLID</span>
              </div>
              <div className="stat-tile">
                <b style={{ color: "var(--decaying)" }}>{graph.summary.decaying}</b>
                <span>DECAYING</span>
              </div>
              <div className="stat-tile">
                <b style={{ color: "var(--struggling)" }}>{graph.summary.gaps}</b>
                <span>GAPS</span>
              </div>
            </div>
          </div>

          <MasteryGraph
            nodes={graph.nodes}
            edges={graph.edges}
            selected={selected}
            onSelect={setSelected}
          />

          <div className="row" style={{ justifyContent: "center", gap: 14, padding: "12px 0 12px" }}>
            <Legend color="var(--ontrack)" label="Solid" />
            <Legend color="var(--decaying)" label="Decaying" />
            <Legend color="var(--struggling)" label="Gap" />
            <Legend color="var(--border)" label="Untouched" />
          </div>

          <ExamPlanner learnerId={learnerId} />
        </>
      )}

      {selectedNode && graph && (
        <NodeSheet
          node={selectedNode}
          graph={graph}
          onClose={() => setSelected(null)}
          onLearn={() => navigate("/")}
        />
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="row" style={{ gap: 6 }}>
      <span
        style={{ width: 11, height: 11, borderRadius: 999, background: color, display: "inline-block" }}
      />
      <span className="faint">{label}</span>
    </span>
  );
}
