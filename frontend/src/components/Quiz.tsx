import { useState } from "react";
import { submitQuizAnswer } from "../api/rest";
import { ArrowIcon, PlayIcon } from "./Icons";
import type { QuizQuestion } from "../types";

const MODALITY_ORDER = ["analogy", "diagram", "video"] as const;

function Reexplanation({ question }: { question: QuizQuestion }) {
  // Escalation ladder: start with the cheapest modality, reveal the next only on request.
  const [tiers, setTiers] = useState(1);
  const available = MODALITY_ORDER.filter((m) => question.reexplanations?.[m]);
  const shown = available.slice(0, tiers);
  const video = question.reexplanations?.video;

  if (available.length === 0) return null;

  return (
    <div style={{ marginTop: 14 }}>
      <span className="eyebrow">Re-explained another way</span>
      <div className="stack" style={{ marginTop: 10 }}>
        {shown.map((modality) => (
          <div key={modality} className="link-row" style={{ gap: 10, alignItems: "flex-start" }}>
            <span className="tag lav">{modality}</span>
            {modality === "video" && video ? (
              <a
                href={video.url}
                target="_blank"
                rel="noreferrer"
                className="row"
                style={{ gap: 6, textDecoration: "none", color: "var(--text)" }}
              >
                <PlayIcon size={13} className="muted" />
                {video.title} @ {video.start_seconds}s
              </a>
            ) : (
              <span style={{ flex: 1, whiteSpace: "pre-wrap" }}>
                {String(question.reexplanations?.[modality] ?? "")}
              </span>
            )}
          </div>
        ))}
      </div>
      {tiers < available.length && (
        <button className="ghost" style={{ marginTop: 8 }} onClick={() => setTiers(tiers + 1)}>
          Still confused? Try the {available[tiers]} →
        </button>
      )}
    </div>
  );
}

function QuestionBlock({
  q,
  index,
  total,
  lessonId,
  onMastery,
}: {
  q: QuizQuestion;
  index: number;
  total: number;
  lessonId?: string;
  onMastery: (score: number) => void;
}) {
  const [revealed, setRevealed] = useState(false);
  const [picked, setPicked] = useState<boolean | null>(null);
  const [outcome, setOutcome] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  const mark = async () => {
    if (!lessonId || saving || picked === null) return;
    setSaving(true);
    setFailed(false);
    try {
      const res = await submitQuizAnswer(lessonId, q.question, picked);
      setOutcome(picked);
      if (res.mastery_score != null) onMastery(res.mastery_score);
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  const optionClass = (value: boolean) => {
    if (outcome !== null) {
      if (outcome !== value) return "option";
      return `option ${value ? "correct" : "wrong"}`;
    }
    return picked === value ? "option selected" : "option";
  };

  return (
    <div className="card animate-in">
      <span className="tag lav" style={{ marginBottom: 12, display: "inline-flex" }}>
        Question {index + 1} of {total}
      </span>
      <h3 style={{ margin: "0 0 14px" }}>{q.question}</h3>

      {!revealed ? (
        <button className="secondary block" onClick={() => setRevealed(true)}>
          Show answer
        </button>
      ) : (
        <>
          <div className="callout lav" style={{ marginBottom: 16 }}>
            <p style={{ margin: 0 }}>{q.answer}</p>
          </div>

          <span className="eyebrow">Grade yourself honestly</span>
          <div className="stack" style={{ marginTop: 10 }}>
            <button
              className={optionClass(true)}
              disabled={outcome !== null || saving}
              onClick={() => setPicked(true)}
            >
              I got it right
            </button>
            <button
              className={optionClass(false)}
              disabled={outcome !== null || saving}
              onClick={() => setPicked(false)}
            >
              I missed it
            </button>
          </div>

          {outcome === null && (
            <>
              <button
                className="block"
                style={{ marginTop: 16 }}
                disabled={!lessonId || saving || picked === null}
                onClick={mark}
              >
                {saving ? "Saving…" : "Check answer"} {!saving && <ArrowIcon size={16} />}
              </button>
              {!lessonId && (
                <span className="faint" style={{ marginTop: 10 }}>
                  Finishing up the session…
                </span>
              )}
              {failed && (
                <span className="faint" style={{ marginTop: 10 }}>
                  Couldn't save — check the backend and try again.
                </span>
              )}
            </>
          )}

          {outcome === false && <Reexplanation question={q} />}
        </>
      )}
    </div>
  );
}

export default function Quiz({
  quiz,
  lessonId,
  onMastery,
}: {
  quiz: QuizQuestion[];
  lessonId?: string;
  onMastery: (score: number) => void;
}) {
  return (
    <>
      <div className="section-head">
        <h2>Check your understanding</h2>
        <span className="faint">{quiz.length} questions</span>
      </div>
      <p className="section-sub">Answer it in your head, reveal, then grade yourself honestly.</p>
      {quiz.map((q, i) => (
        <QuestionBlock
          key={i}
          q={q}
          index={i}
          total={quiz.length}
          lessonId={lessonId}
          onMastery={onMastery}
        />
      ))}
    </>
  );
}
