import ProgressRing from "./ProgressRing";
import type { LessonContent } from "../types";

const TOTAL_STEPS = 4;

export default function Lesson({
  lesson,
  stepsDone = 1,
}: {
  lesson: LessonContent;
  stepsDone?: number;
}) {
  return (
    <div style={{ marginTop: 22 }}>
      <div className="card animate-in">
        <span className="tag lav" style={{ marginBottom: 12, display: "inline-flex" }}>
          {lesson.topic_name}
        </span>
        <h2 style={{ margin: "0 0 10px" }}>Conceptual Overview</h2>
        <p style={{ margin: 0 }}>{lesson.overview}</p>

        {lesson.worked_examples?.length > 0 && (
          <div style={{ marginTop: 10 }}>
            {lesson.worked_examples.map((ex, i) => (
              <div key={i} className="example">
                <span className="pill-label">{ex.difficulty}</span>
                <strong style={{ display: "block", marginBottom: 5 }}>{ex.prompt}</strong>
                <p className="muted" style={{ margin: 0 }}>
                  {ex.solution}
                </p>
              </div>
            ))}
          </div>
        )}

        {lesson.common_mistakes?.length > 0 && (
          <>
            <div className="divider" />
            <strong>Common mistakes</strong>
            <div className="stack" style={{ marginTop: 10 }}>
              {lesson.common_mistakes.map((m, i) => (
                <div key={i} className="row" style={{ gap: 9, alignItems: "flex-start" }}>
                  <span style={{ color: "var(--struggling)", fontWeight: 700, lineHeight: 1.5 }}>
                    ·
                  </span>
                  <span className="muted" style={{ flex: 1, fontSize: 14 }}>
                    {m}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card animate-in">
        <div className="row" style={{ gap: 14, flexWrap: "nowrap" }}>
          <ProgressRing value={stepsDone} total={TOTAL_STEPS} />
          <div style={{ minWidth: 0 }}>
            <strong style={{ display: "block", fontSize: 15 }}>
              {stepsDone >= TOTAL_STEPS ? "Package complete" : "Lesson complete"}
            </strong>
            <span className="faint">Ready to test your knowledge?</span>
          </div>
        </div>
      </div>
    </div>
  );
}
