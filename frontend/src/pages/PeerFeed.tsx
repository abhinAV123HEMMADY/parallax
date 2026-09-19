import { useEffect, useState } from "react";
import { getSquadProposals, getStruggleFeed, postQna } from "../api/rest";
import SquadCard from "../components/SquadCard";
import StruggleHeatmap from "../components/StruggleHeatmap";
import { ArrowIcon, ChatIcon, CheckIcon, PeerIcon } from "../components/Icons";
import { useLearner } from "../LearnerContext";
import type { SquadProposal, StruggleFeedItem } from "../types";

const SIGNAL_LABEL: Record<string, string> = {
  struggling: "stuck",
  on_track: "on track",
};

export default function PeerFeed() {
  const { learnerId } = useLearner();
  const [feed, setFeed] = useState<StruggleFeedItem[]>([]);
  const [squads, setSquads] = useState<SquadProposal[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [qnaBody, setQnaBody] = useState("");
  const [qnaStatus, setQnaStatus] = useState<string | null>(null);
  const [qnaError, setQnaError] = useState(false);

  useEffect(() => {
    setLoadError(false);
    Promise.all([getStruggleFeed(learnerId), getSquadProposals("derivatives")])
      .then(([feedRes, squadsRes]) => {
        setFeed(feedRes);
        setSquads(squadsRes);
      })
      .catch(() => setLoadError(true));
  }, [learnerId]);

  const submitQna = async () => {
    if (!qnaBody.trim()) return;
    setQnaError(false);
    try {
      const res = await postQna("derivatives", learnerId, qnaBody.trim());
      setQnaStatus(res.moderation_status);
      setQnaBody("");
    } catch {
      setQnaError(true);
    }
  };

  return (
    <div>
      <div className="page-title">
        <h1>Peer Struggle Feed</h1>
        <p>
          Connect with peers facing similar academic challenges and overcome them together.
        </p>
      </div>

      {loadError && (
        <div className="callout warn animate-in">
          <span className="eyebrow">Couldn't load the peer feed</span>
          <p style={{ margin: "6px 0 0" }}>
            Make sure the backend is running, then reload this page.
          </p>
        </div>
      )}

      <StruggleHeatmap items={feed} />

      {feed.length > 0 && (
        <div className="stack stagger" style={{ marginTop: 14 }}>
          {feed.map((item, i) => (
            <div key={`${item.user_id}-${i}`} className="card" style={{ marginBottom: 0 }}>
              <div className="row" style={{ gap: 12, flexWrap: "nowrap" }}>
                <span className="avatar">
                  {item.user_id.replace("u_", "").charAt(0).toUpperCase()}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                    <strong style={{ fontSize: 14.5 }}>{item.user_id.replace("u_", "@")}</strong>
                    <span className={`tag ${item.relative_signal}`}>
                      {SIGNAL_LABEL[item.relative_signal] ?? item.relative_signal.replace("_", " ")}
                    </span>
                  </div>
                  <span className="faint">In your cohort</span>
                </div>
              </div>

              <p style={{ margin: "12px 0 14px" }}>
                Hitting friction on{" "}
                <strong style={{ color: "var(--primary-bright)", textTransform: "capitalize" }}>
                  {item.topic_name}
                </strong>{" "}
                — the same node you've been working through.
              </p>

              <div className="row" style={{ gap: 8 }}>
                <button className="violet sm">
                  <PeerIcon size={14} /> Join squad
                </button>
                <button className="secondary sm">
                  <ChatIcon size={14} /> Comment
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="section-head">
        <h2>Study squads</h2>
        <span className="faint">auto-formed</span>
      </div>
      {squads.length === 0 ? (
        <div className="card empty" style={{ marginBottom: 0 }}>
          <span className="emoji">🧩</span>
          No squad yet for “derivatives” — needs 3+ connected learners struggling on the same node.
        </div>
      ) : (
        <div className="stagger">
          {squads.map((s) => (
            <SquadCard key={s.id} squad={s} />
          ))}
        </div>
      )}

      <div className="section-head">
        <h2>Ask the group</h2>
        <span className="faint">derivatives</span>
      </div>
      <div className="card">
        <div className="stack">
          <textarea
            rows={3}
            placeholder="Ask the group a question…"
            value={qnaBody}
            onChange={(e) => setQnaBody(e.target.value)}
            style={{ resize: "none" }}
          />
          <button className="block" onClick={submitQna} disabled={!qnaBody.trim()}>
            Post to feed <ArrowIcon size={16} />
          </button>
        </div>
        {qnaError && (
          <span className="faint" style={{ marginTop: 12 }}>
            Couldn't post — check the backend and try again.
          </span>
        )}
        {qnaStatus && (
          <span className="faint" style={{ marginTop: 12 }}>
            <CheckIcon size={13} /> Moderation: {qnaStatus} — screened before peers see it.
          </span>
        )}
      </div>
    </div>
  );
}
