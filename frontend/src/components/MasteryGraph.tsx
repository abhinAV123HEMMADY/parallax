import { useMemo } from "react";
import type { MasteryEdge, MasteryNode } from "../types";

const W = 340;
const ROW_H = 120;
const TOP = 58;

interface Placed extends MasteryNode {
  x: number;
  y: number;
  r: number;
}

function layout(nodes: MasteryNode[], edges: MasteryEdge[]): { placed: Placed[]; height: number } {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const parents = new Map<string, string[]>();
  nodes.forEach((n) => parents.set(n.id, []));
  edges.forEach((e) => {
    if (byId.has(e.from) && byId.has(e.to)) parents.get(e.to)!.push(e.from);
  });

  // longest-path depth (topological; graph is a DAG)
  const depth = new Map<string, number>();
  const visit = (id: string): number => {
    if (depth.has(id)) return depth.get(id)!;
    const ps = parents.get(id) ?? [];
    const d = ps.length === 0 ? 0 : Math.max(...ps.map(visit)) + 1;
    depth.set(id, d);
    return d;
  };
  nodes.forEach((n) => visit(n.id));

  const byDepth = new Map<number, MasteryNode[]>();
  nodes.forEach((n) => {
    const d = depth.get(n.id)!;
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d)!.push(n);
  });

  const placed: Placed[] = [];
  byDepth.forEach((group, d) => {
    group.forEach((n, i) => {
      placed.push({
        ...n,
        x: (W / (group.length + 1)) * (i + 1),
        y: TOP + d * ROW_H,
        r: 16 + n.effective_mastery * 20,
      });
    });
  });

  const maxDepth = Math.max(0, ...[...depth.values()]);
  return { placed, height: TOP + maxDepth * ROW_H + 64 };
}

function wrap(name: string): string[] {
  if (name.length <= 13) return [name];
  const words = name.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > 13) {
      if (cur) lines.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 2);
}

export default function MasteryGraph({
  nodes,
  edges,
  selected,
  onSelect,
}: {
  nodes: MasteryNode[];
  edges: MasteryEdge[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { placed, height } = useMemo(() => layout(nodes, edges), [nodes, edges]);
  const pos = new Map(placed.map((p) => [p.id, p]));

  return (
    <div className="graph-wrap animate-in">
      <svg className="graph-svg" viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Mastery map">
        {edges.map((e, i) => {
          const a = pos.get(e.from);
          const b = pos.get(e.to);
          if (!a || !b) return null;
          const blocked = a.status === "gap" || a.status === "weak";
          const midY = (a.y + a.r + (b.y - b.r)) / 2;
          return (
            <path
              key={i}
              className={`edge ${blocked ? "blocked" : ""}`}
              d={`M ${a.x} ${a.y + a.r} C ${a.x} ${midY}, ${b.x} ${midY}, ${b.x} ${b.y - b.r}`}
            />
          );
        })}

        {placed.map((n) => {
          const lines = wrap(n.name);
          const isSel = selected === n.id;
          return (
            <g
              key={n.id}
              className="node-hit"
              onClick={() => onSelect(n.id)}
              transform={`translate(${n.x} ${n.y})`}
            >
              {isSel && <circle className="ring-sel" r={n.r + 7} />}
              {n.status === "decaying" && <circle className="ring-decay" r={n.r + 5} />}
              {(n.status === "gap" || n.status === "weak") && (
                <circle className="ring-gap" r={n.r + 6} />
              )}
              <circle className={`node-core n-${n.status}`} r={n.r} />
              <text
                textAnchor="middle"
                dy="0.35em"
                style={{ fontWeight: 800, fontSize: 13, fill: "var(--on-primary)" }}
              >
                {n.status === "untouched" ? "" : `${Math.round(n.effective_mastery * 100)}`}
              </text>
              {lines.map((line, li) => (
                <text
                  key={li}
                  className="node-label"
                  textAnchor="middle"
                  y={n.r + 16 + li * 13}
                >
                  {line}
                </text>
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
