import { useRef, useState } from "react";
import { publishProtegeExplanation, sendProtegeTurn, startProtege } from "../api/rest";
import { ArrowIcon, ChatIcon, CheckIcon } from "../components/Icons";
import { useLearner } from "../LearnerContext";
import type { ChatMessage, ChecklistItem } from "../types";

const UNDERSTANDING_THRESHOLD = 0.75;

export default function ProtegeMode() {
  const { learnerId, lastTopic, setLastTopic } = useLearner();
  const [topicInput, setTopicInput] = useState(lastTopic);
  const [topicName, setTopicName] = useState(lastTopic);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [understandingScore, setUnderstandingScore] = useState(0);
  const [status, setStatus] = useState<"idle" | "active" | "completed" | "published">("idle");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToEnd = () => {
    requestAnimationFrame(() => threadEndRef.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const start = async () => {
    if (!topicInput.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await startProtege(topicInput.trim(), learnerId);
      setSessionId(res.session_id);
      setTopicName(res.topic_name);
      setLastTopic(res.topic_name);
      setMessages([{ role: "persona", content: res.persona_message }]);
      setChecklist(res.checklist);
      setUnderstandingScore(res.understanding_score);
      setStatus("active");
      setPublishStatus(null);
      scrollToEnd();
    } catch {
      setError("Couldn't reach the backend — make sure it's running, then try again.");
    } finally {
      setBusy(false);
    }
  };

  const restart = () => {
    setSessionId(null);
    setStatus("idle");
    setMessages([]);
    setError(null);
  };

  const send = async (overrideText?: string) => {
    const explanation = (overrideText ?? input).trim();
    if (!sessionId || !explanation || busy) return;
    setMessages((prev) => [...prev, { role: "learner", content: explanation }]);
    setInput("");
    setBusy(true);
    setError(null);
    scrollToEnd();
    try {
      const res = await sendProtegeTurn(sessionId, explanation);
      setMessages((prev) => [...prev, { role: "persona", content: res.persona_message }]);
      setChecklist(res.checklist);
      setUnderstandingScore(res.understanding_score);
      setStatus(res.status);
      scrollToEnd();
    } catch {
      setError("Couldn't reach the backend — your explanation wasn't scored. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!sessionId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await publishProtegeExplanation(sessionId);
      setPublishStatus(res.moderation_status);
      setStatus("published");
    } catch {
      setError("Couldn't publish — check the backend and try again.");
    } finally {
      setBusy(false);
    }
  };

  const coveredCount = checklist.filter((c) => c.covered).length;
  const canPublish = status === "completed" && understandingScore >= UNDERSTANDING_THRESHOLD;

  return (
    <div>
      <div className="page-title">
        <span className="eyebrow">
          <ChatIcon size={13} /> Protégé Mode
        </span>
        <h1 style={{ marginTop: 6 }}>
          Teach Mentra {status === "idle" ? topicInput || "…" : topicName}
        </h1>
      </div>

      {error && (
        <div className="callout warn animate-in">
          <span className="eyebrow">Something went wrong</span>
          <p style={{ margin: "6px 0 0" }}>{error}</p>
        </div>
      )}

      {status === "idle" && (
        <div className="card animate-in">
          <h3 style={{ marginTop: 0 }}>Mentra plays a confused student</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            It genuinely holds a few real misconceptions about the topic below and will ask
            naive follow-up questions until your explanation actually resolves them. Teaching it
            cements your own understanding — and produces a mastery signal harder to fake than a
            quiz answer.
          </p>
          <div className="stack">
            <input
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              placeholder="e.g. derivatives, photosynthesis, the French Revolution…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && topicInput.trim() && !busy) start();
              }}
            />
            <button className="block" disabled={busy || !topicInput.trim()} onClick={start}>
              {busy ? "Starting…" : "Start teaching"}
              {!busy && <ArrowIcon size={17} />}
            </button>
          </div>
          <span className="faint" style={{ marginTop: 12 }}>
            Defaults to whatever you last learned on the Learn page.
          </span>
        </div>
      )}

      {status !== "idle" && (
        <>
          <div className="card animate-in">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>Understanding</h3>
              <strong style={{ fontSize: 22, letterSpacing: "-0.02em" }}>
                {Math.round(understandingScore * 100)}%
              </strong>
            </div>
            <div className="meter" style={{ marginTop: 14 }}>
              <span style={{ width: `${Math.min(100, Math.max(4, understandingScore * 100))}%` }} />
            </div>
            <div className="chip-row" style={{ marginTop: 14, gap: 6 }}>
              {checklist.map((item) => (
                <span key={item.id} className={`tag ${item.covered ? "on_track" : "neutral"}`}>
                  {item.covered && <CheckIcon size={12} />}
                  {item.sub_concept}
                </span>
              ))}
            </div>
            <span className="faint" style={{ marginTop: 12 }}>
              {coveredCount}/{checklist.length} misconceptions resolved
            </span>
          </div>

          <div className="card animate-in">
            <div className="chat-thread">
              {messages.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.content}
                </div>
              ))}
              <div ref={threadEndRef} />
            </div>

            {status !== "published" && (
              <div className="stack">
                <textarea
                  rows={3}
                  placeholder="Explain it back to your confused peer…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={busy || status === "completed"}
                  style={{ resize: "none" }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && input.trim() && !busy && status === "active") {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="row">
                  <button
                    className="secondary"
                    disabled={busy || status !== "active"}
                    onClick={() => send("I don't know")}
                    title="Get a hint on the current misconception instead of guessing"
                  >
                    I don't know
                  </button>
                  <button
                    style={{ flex: 1 }}
                    disabled={busy || !input.trim() || status !== "active"}
                    onClick={() => send()}
                  >
                    {busy ? "Thinking…" : "Send explanation"}
                    {!busy && <ArrowIcon size={17} />}
                  </button>
                </div>
              </div>
            )}

            {status === "completed" && (
              <div className="callout lav" style={{ marginTop: 14, marginBottom: 0 }}>
                <span className="eyebrow">Session complete</span>
                <p style={{ margin: "6px 0 0" }}>
                  {canPublish
                    ? "Your explanation cleared the understanding threshold — publish it to the Q&A feed so other learners struggling with the same misconceptions can see it."
                    : "Session ended before every misconception was resolved — start a new session to try again."}
                </p>
                <div className="row" style={{ marginTop: 12 }}>
                  {canPublish && (
                    <button disabled={busy} onClick={publish}>
                      {busy ? "Publishing…" : "Publish this explanation"}
                    </button>
                  )}
                  <button className="secondary" disabled={busy} onClick={restart}>
                    New session
                  </button>
                </div>
              </div>
            )}

            {status === "published" && (
              <div className="card" style={{ marginTop: 14, marginBottom: 0 }}>
                <span className="tag on_track">
                  <CheckIcon size={13} /> Moderation: {publishStatus}
                </span>
                <p className="faint" style={{ marginTop: 10, marginBottom: 12 }}>
                  Posted to the {topicName} Q&A feed as a peer explanation.
                </p>
                <button className="secondary" disabled={busy} onClick={restart}>
                  New session
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
