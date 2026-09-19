import { ArrowIcon } from "./Icons";
import type { SquadProposal } from "../types";

const AVATAR_TINTS = ["#6d5ae0", "#3a2d7d", "#a8407a", "#2f7d52"];

export default function SquadCard({ squad }: { squad: SquadProposal }) {
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <strong style={{ fontSize: 14.5, textTransform: "capitalize" }}>{squad.topic_id}</strong>
        <span className="tag lav">{squad.member_ids.length} members</span>
      </div>
      <p style={{ margin: "0 0 14px" }}>
        Shared flashcard deck seeded from the group's weakest cards.
      </p>

      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <div className="row" style={{ gap: 0, flexWrap: "nowrap" }}>
          {squad.member_ids.map((id, i) => (
            <span
              key={id}
              className="avatar"
              style={{
                marginLeft: i === 0 ? 0 : -12,
                border: "2px solid var(--surface)",
                background: AVATAR_TINTS[i % AVATAR_TINTS.length],
                fontSize: 13,
                width: 34,
                height: 34,
              }}
              title={id}
            >
              {id.replace("u_", "").charAt(0).toUpperCase()}
            </span>
          ))}
        </div>
        <button className="violet sm">
          Enter study room <ArrowIcon size={14} />
        </button>
      </div>
    </div>
  );
}
