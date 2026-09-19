import { useNavigate } from "react-router-dom";
import { ArrowIcon, CameraIcon, CheckIcon, CloseIcon } from "./Icons";
import type { ErrorAnalysis } from "../types";

export default function ErrorAnalysisCard({ analysis }: { analysis: ErrorAnalysis }) {
  const navigate = useNavigate();
  const hasError = analysis.first_error_step >= 0;

  return (
    <div className="card animate-in" style={{ marginTop: 22 }}>
      <span className="eyebrow">
        <CameraIcon size={13} /> Snapped work · error localized
      </span>
      <div className="formula" style={{ margin: "12px 0 4px" }}>
        {analysis.problem_statement}
      </div>

      <div className="stack" style={{ marginTop: 14, gap: 8 }}>
        {analysis.steps.map((step, i) => {
          const wrong = i === analysis.first_error_step;
          return (
            <div
              key={i}
              className="row"
              style={{
                alignItems: "flex-start",
                gap: 10,
                padding: "11px 13px",
                borderRadius: "var(--r-md)",
                background: wrong ? "var(--struggling-bg)" : "var(--surface-2)",
                border: wrong ? "1px solid var(--struggling)" : "1px solid transparent",
              }}
            >
              <span style={{ color: wrong ? "var(--struggling)" : "var(--ontrack)", flexShrink: 0, marginTop: 2 }}>
                {wrong ? <CloseIcon size={14} /> : <CheckIcon size={14} />}
              </span>
              <span style={{ minWidth: 0 }}>
                <code style={{ display: "block" }}>{step.text}</code>
                {wrong && step.note && (
                  <span className="faint" style={{ display: "block", marginTop: 4 }}>
                    {step.note}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>

      {hasError ? (
        <>
          <p className="muted" style={{ marginTop: 12 }}>
            {analysis.error_explanation}
          </p>
          <div className="callout lav" style={{ marginTop: 12, marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
              <span style={{ minWidth: 0 }}>
                Gap traced to{" "}
                <strong style={{ textTransform: "capitalize" }}>
                  {analysis.prerequisite_concept}
                </strong>
                <span className="faint" style={{ display: "block" }}>
                  not {analysis.tested_concept} itself — your map has been updated
                </span>
              </span>
              <button className="violet sm" onClick={() => navigate("/map")} style={{ flexShrink: 0 }}>
                See map <ArrowIcon size={14} />
              </button>
            </div>
          </div>
        </>
      ) : (
        <p className="muted" style={{ marginTop: 12 }}>
          Every step checks out — this attempt was correct.
        </p>
      )}
    </div>
  );
}
