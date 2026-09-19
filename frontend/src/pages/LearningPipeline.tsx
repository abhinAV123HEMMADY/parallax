import { useRef, useState } from "react";
import { subscribeToSession } from "../api/ws";
import { startLearning } from "../api/rest";
import ErrorAnalysisCard from "../components/ErrorAnalysisCard";
import Flashcards from "../components/Flashcards";
import Lesson from "../components/Lesson";
import Quiz from "../components/Quiz";
import { AlertIcon, ArrowIcon, PlayIcon, StarIcon } from "../components/Icons";
import { useLearner } from "../LearnerContext";
import type { LearningSessionData, PipelineUpdate } from "../types";
import TopicInput from "./TopicInput";

const emptyData: LearningSessionData = { done: false };

const STEP_LABELS = ["Lesson", "Quiz", "Cards", "Sources"];

export default function LearningPipeline() {
  const { learnerId, setLastTopic } = useLearner();
  const [data, setData] = useState<LearningSessionData>(emptyData);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Only real interactions move this: quiz answers, card reviews (server-recomputed each time).
  const [mastery, setMastery] = useState<number | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  const handleUpdate = ({ node, update }: PipelineUpdate) => {
    if (node === "_done") {
      setRunning(false);
      setData((prev) => ({ ...prev, done: true }));
      return;
    }
    setData((prev) => ({ ...prev, ...update, done: false }));
    const topicName = (update as { lesson?: { topic_name?: string } }).lesson?.topic_name;
    if (topicName) setLastTopic(topicName);
  };

  const onSubmit = async (topic: string, mode: "text" | "photo") => {
    cleanupRef.current?.();
    setData(emptyData);
    setError(null);
    setMastery(null);
    setRunning(true);
    setLastTopic(topic);

    try {
      const { session_id } = await startLearning(learnerId, topic, mode);
      cleanupRef.current = subscribeToSession(session_id, handleUpdate);
    } catch {
      setRunning(false);
      setError("Couldn't reach the backend — make sure it's running, then try again.");
    }
  };

  const stepDone = [
    !!data.lesson?.overview,
    !!(data.quiz && data.quiz.length),
    !!(data.flashcards && data.flashcards.length),
    !!(data.videos && data.videos.length) || !!(data.tutor_matches && data.tutor_matches.length),
  ];
  const activeStep = stepDone.findIndex((d) => !d);

  return (
    <div>
      <TopicInput onSubmit={onSubmit} disabled={running} />

      {error && (
        <div className="callout warn animate-in" style={{ marginTop: 18 }}>
          <span className="eyebrow">Couldn't generate a lesson</span>
          <p style={{ margin: "6px 0 0" }}>{error}</p>
        </div>
      )}

      {running && (
        <div className="card animate-in" style={{ marginTop: 22 }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
            <strong style={{ fontSize: 14 }}>Building your package…</strong>
            <span className="faint">streaming live</span>
          </div>
          <div className="stepper">
            {STEP_LABELS.map((label, i) => (
              <div key={label} style={{ display: "contents" }}>
                {i > 0 && <span className="stepper-line" />}
                <div className={`stepper-item ${stepDone[i] || i === activeStep ? "on" : ""}`}>
                  <span className="stepper-dot">{i + 1}</span>
                  {label}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.error_analysis && <ErrorAnalysisCard analysis={data.error_analysis} />}

      {data.prerequisite_gap && (
        <div className="callout animate-in" style={{ marginTop: 18 }}>
          <span className="eyebrow">
            <AlertIcon size={16} /> Prerequisite Alert
          </span>
          <p style={{ margin: "8px 0 0" }}>
            Your mastery on{" "}
            <strong style={{ textTransform: "capitalize" }}>{data.prerequisite_gap}</strong> is
            below threshold, so this lesson targets the real upstream gap instead of the topic you
            asked for.
          </p>
        </div>
      )}

      {data.lesson?.overview && (
        <Lesson lesson={data.lesson} stepsDone={stepDone.filter(Boolean).length} />
      )}

      {data.quiz && data.quiz.length > 0 && (
        <Quiz quiz={data.quiz} lessonId={data.lesson?.lesson_id} onMastery={setMastery} />
      )}

      {data.flashcards && data.flashcards.length > 0 && (
        <Flashcards cards={data.flashcards} onMastery={setMastery} />
      )}

      {data.videos && data.videos.length > 0 && (
        <>
          <div className="section-head">
            <h3>Jump to the moment</h3>
            <span className="faint">timestamped</span>
          </div>
          <div className="stack">
            {data.videos.map((v) => (
              <a
                key={`${v.video_id}-${v.start_seconds}`}
                className="link-row"
                href={v.url}
                target="_blank"
                rel="noreferrer"
              >
                <span className="play-badge">
                  <PlayIcon />
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ display: "block" }}>{v.title}</strong>
                  <span className="faint">
                    @ {Math.floor(v.start_seconds / 60)}:
                    {String(v.start_seconds % 60).padStart(2, "0")} · relevance{" "}
                    {v.relevance.toFixed(2)}
                  </span>
                </span>
                <ArrowIcon size={16} className="muted" />
              </a>
            ))}
          </div>
        </>
      )}

      {data.tutor_matches && data.tutor_matches.length > 0 && (
        <>
          <div className="section-head">
            <h3>Human help on this topic</h3>
          </div>
          <div className="stack">
            {data.tutor_matches.map((t) => (
              <div key={t.id} className="link-row">
                <span className="avatar">{t.name.charAt(0)}</span>
                <span style={{ flex: 1 }}>
                  <strong style={{ display: "block" }}>{t.name}</strong>
                  <span className="faint">
                    <StarIcon size={12} /> {t.rating.toFixed(1)} · ${t.price_per_hour}/hr
                  </span>
                </span>
                <span className="tag on_track">{t.verification_tier.replace("_", " ")}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {data.quiz && data.quiz.length > 0 && (
        <div className="card animate-in" style={{ marginTop: 22 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>Mastery</h3>
            <strong style={{ fontSize: 22, letterSpacing: "-0.02em" }}>
              {Math.round((mastery ?? 0) * 100)}%
            </strong>
          </div>
          <div className="meter" style={{ marginTop: 14 }}>
            <span
              style={{ width: `${Math.min(100, Math.max(mastery ? 4 : 0, (mastery ?? 0) * 100))}%` }}
            />
          </div>
          <p className="faint" style={{ marginTop: 12, marginBottom: 0, display: "block" }}>
            {mastery === null
              ? "Nothing earned yet — answer the quiz and review the cards; this fills only from what you actually demonstrate."
              : "Recomputed from your real quiz answers, card reviews, and teach-back sessions."}
          </p>
        </div>
      )}

      {data.done && (
        <p className="faint" style={{ display: "block", textAlign: "center", padding: "8px 0 4px" }}>
          ✓ Session complete
        </p>
      )}
    </div>
  );
}
