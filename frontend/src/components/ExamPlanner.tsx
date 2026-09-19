import { useEffect, useState } from "react";
import { getExamPlan } from "../api/rest";
import { SparkleIcon } from "./Icons";
import type { ExamPlan } from "../types";

const W = 320;
const H = 150;
const PAD = { top: 12, right: 14, bottom: 30, left: 34 };
const LOAD_H = 16; // review-load bars live in the bottom strip of the plot area

function Chart({ plan }: { plan: ExamPlan }) {
  const days = plan.days_until_exam;
  const all = [...plan.curve_baseline, ...plan.curve_exam_aware];
  const yMin = Math.max(0, Math.floor((Math.min(...all) - 0.03) * 20) / 20);
  const yMax = 1.0;

  const x = (day: number) => PAD.left + (day / days) * (W - PAD.left - PAD.right);
  const y = (r: number) =>
    PAD.top + (1 - (r - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom - LOAD_H);

  const path = (curve: number[]) => curve.map((r, d) => `${d === 0 ? "M" : "L"}${x(d).toFixed(1)},${y(r).toFixed(1)}`).join(" ");

  const maxLoad = Math.max(...plan.daily_load, 1);
  const loadTop = H - PAD.bottom;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", display: "block" }} role="img" aria-label="Projected retention curve, standard vs exam-aware schedule">
      {[yMin, (yMin + 1) / 2, 1].map((r) => (
        <g key={r}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(r)} y2={y(r)} stroke="var(--border)" strokeWidth={0.6} strokeDasharray="2 3" />
          <text x={PAD.left - 5} y={y(r) + 3} fontSize={7.5} fill="var(--faint)" textAnchor="end">
            {Math.round(r * 100)}%
          </text>
        </g>
      ))}

      {/* review-load bars for the exam-aware plan */}
      {plan.daily_load.map((n, d) =>
        n === 0 ? null : (
          <rect
            key={d}
            x={x(d) - 2}
            width={4}
            y={loadTop - (n / maxLoad) * LOAD_H}
            height={(n / maxLoad) * LOAD_H}
            rx={1.5}
            fill="var(--chip-lav-fg)"
            opacity={0.45}
          />
        ),
      )}

      {/* exam-day marker */}
      <line x1={x(days)} x2={x(days)} y1={PAD.top} y2={loadTop} stroke="var(--struggling)" strokeWidth={0.8} strokeDasharray="3 3" />
      <text x={x(days)} y={H - 18} fontSize={7.5} fill="var(--struggling)" textAnchor="end">
        exam
      </text>
      <text x={PAD.left} y={H - 18} fontSize={7.5} fill="var(--faint)">
        today
      </text>

      <path d={path(plan.curve_baseline)} fill="none" stroke="var(--muted)" strokeWidth={1.4} strokeDasharray="4 3" strokeLinecap="round" />
      <path d={path(plan.curve_exam_aware)} fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinecap="round" />
      <circle cx={x(days)} cy={y(plan.curve_exam_aware[days])} r={3.4} fill="var(--primary)" stroke="var(--surface)" strokeWidth={1.4} />

      {/* legend */}
      <g fontSize={7.5}>
        <line x1={PAD.left + 4} x2={PAD.left + 18} y1={H - 5} y2={H - 5} stroke="var(--primary)" strokeWidth={2} strokeLinecap="round" />
        <text x={PAD.left + 22} y={H - 2.5} fill="var(--muted)">exam-aware</text>
        <line x1={PAD.left + 82} x2={PAD.left + 96} y1={H - 5} y2={H - 5} stroke="var(--muted)" strokeWidth={1.4} strokeDasharray="4 3" />
        <text x={PAD.left + 100} y={H - 2.5} fill="var(--muted)">standard FSRS</text>
      </g>
    </svg>
  );
}

export default function ExamPlanner({ learnerId }: { learnerId: string }) {
  const [days, setDays] = useState(14);
  const [plan, setPlan] = useState<ExamPlan | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let stale = false;
    setError(false);
    getExamPlan(learnerId, days)
      .then((p) => {
        if (!stale) setPlan(p);
      })
      .catch(() => {
        if (!stale) setError(true);
      });
    return () => {
      stale = true;
    };
  }, [learnerId, days]);

  const reviewsPlanned = plan ? plan.daily_load.reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="card animate-in">
      <span className="eyebrow">
        <SparkleIcon size={13} /> Peak on the day
      </span>
      <h3 style={{ marginTop: 10 }}>Exam-aware scheduling</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Standard spaced repetition optimizes forever-retention. Set an exam date and Mentra
        bends the tail of the schedule so your memory peaks when it counts.
      </p>

      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <span className="faint">Exam in</span>
        <strong>{days} days</strong>
      </div>
      <input
        type="range"
        min={5}
        max={45}
        value={days}
        onChange={(e) => setDays(Number(e.target.value))}
        aria-label="Days until exam"
        style={{ width: "100%" }}
      />

      {error ? (
        <p className="faint" style={{ marginTop: 12, marginBottom: 0 }}>
          Couldn't load an exam plan — make sure the backend is running.
        </p>
      ) : !plan ? (
        <div className="skeleton" style={{ height: 150, marginTop: 12 }} />
      ) : (
        <>
          <div style={{ marginTop: 12 }}>
            <Chart plan={plan} />
          </div>
          <div className="stat-row" style={{ gridTemplateColumns: "repeat(3,1fr)", marginTop: 12 }}>
            <div className="stat-tile">
              <b style={{ color: "var(--ontrack)" }}>{Math.round(plan.exam_day.exam_aware * 100)}%</b>
              <span>EXAM-DAY RETENTION</span>
            </div>
            <div className="stat-tile">
              <b className="muted">{Math.round(plan.exam_day.baseline * 100)}%</b>
              <span>WITHOUT PLANNING</span>
            </div>
            <div className="stat-tile">
              <b>{reviewsPlanned}</b>
              <span>REVIEWS PLANNED</span>
            </div>
          </div>
          <p className="faint" style={{ marginTop: 10, marginBottom: 0 }}>
            {plan.exam_day.cards_at_risk_baseline} card
            {plan.exam_day.cards_at_risk_baseline === 1 ? "" : "s"} would arrive at the exam
            below 90% recall — the plan rescues{" "}
            {plan.exam_day.cards_at_risk_baseline - plan.exam_day.cards_at_risk_exam_aware} of
            them with load-balanced consolidation reviews (bars).
            {plan.demo_deck ? " Planning over a sample deck — generate a lesson to build yours." : ""}
          </p>
        </>
      )}
    </div>
  );
}
