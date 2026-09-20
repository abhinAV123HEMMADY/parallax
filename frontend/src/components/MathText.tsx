import katex from "katex";
import { useMemo } from "react";

// The models write math as LaTeX — \(x^n\), \frac{dy}{dx}, $$...$$ — which read as literal
// backslashes before this existed. Everything outside a delimiter stays plain text and is
// never passed to dangerouslySetInnerHTML, so only KaTeX's own output is injected, and KaTeX
// renders with trust disabled by default.
const SEGMENT = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\))/g;

type Segment = { kind: "text" | "math"; body: string; display: boolean };

function parse(input: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const match of input.matchAll(SEGMENT)) {
    const start = match.index ?? 0;
    if (start > last) out.push({ kind: "text", body: input.slice(last, start), display: false });

    const raw = match[0];
    let body = raw;
    let display = false;
    if (raw.startsWith("$$")) {
      body = raw.slice(2, -2);
      display = true;
    } else if (raw.startsWith("\\[")) {
      body = raw.slice(2, -2);
      display = true;
    } else if (raw.startsWith("\\(")) {
      body = raw.slice(2, -2);
    } else if (raw.startsWith("$")) {
      body = raw.slice(1, -1);
    }
    out.push({ kind: "math", body, display });
    last = start + raw.length;
  }
  if (last < input.length) out.push({ kind: "text", body: input.slice(last), display: false });
  return out;
}

export default function MathText({ children }: { children: string }) {
  const segments = useMemo(() => parse(children ?? ""), [children]);

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === "text") return <span key={i}>{seg.body}</span>;
        let html: string;
        try {
          html = katex.renderToString(seg.body, {
            displayMode: seg.display,
            throwOnError: false,
            output: "html",
          });
        } catch {
          // Malformed LaTeX shows as the source rather than blanking the sentence around it.
          return <span key={i}>{seg.body}</span>;
        }
        return (
          <span
            key={i}
            className={seg.display ? "math-display" : "math-inline"}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </>
  );
}
