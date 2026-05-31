"use client";

// Avatar fourmi animé piloté par l'état (porté du design mc-ants.jsx).
// États : working · sleeping (idle/stale) · happy (done) · searching (blocked/error).

export type AntMood = "working" | "sleeping" | "happy" | "searching";

export function antStateOf(state: string): AntMood {
  switch (state) {
    case "working": return "working";
    case "done": return "happy";
    case "blocked":
    case "error": return "searching";
    case "idle":
    case "stale": return "sleeping";
    default: return "working";
  }
}

export function Ant({
  state = "working",
  color = "currentColor",
  size = 30,
}: {
  state?: AntMood;
  color?: string;
  size?: number;
}) {
  return (
    <svg
      className={"ant ant-" + state + " on"}
      width={size}
      height={size}
      viewBox="0 0 44 44"
      style={{ color, display: "block", overflow: "visible" }}
      aria-hidden="true"
    >
      <ellipse className="ant-shadow" cx="20" cy="37" rx="13" ry="2.4" fill="currentColor" opacity=".14" />
      <g className="ant-body">
        <g className="ant-legs" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <path className="lg l1" d="M19 26 L13 31 L11 35" />
          <path className="lg l2" d="M22 27 L20 32 L19 36" />
          <path className="lg l3" d="M25 26 L27 32 L27 36" />
        </g>
        <g className="ant-ant" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <path d="M31 16 Q34 10 37 9" />
          <circle cx="37.4" cy="8.7" r="1.3" fill="currentColor" stroke="none" />
        </g>
        <ellipse className="seg abdomen" cx="13" cy="24" rx="8.5" ry="6.4" fill="currentColor" fillOpacity=".22" stroke="currentColor" strokeWidth="1.7" />
        <ellipse className="seg thorax" cx="23.5" cy="23" rx="4.6" ry="4.4" fill="currentColor" fillOpacity=".22" stroke="currentColor" strokeWidth="1.7" />
        <circle className="seg head" cx="31" cy="20.5" r="4.8" fill="currentColor" fillOpacity=".22" stroke="currentColor" strokeWidth="1.7" />
        {state === "sleeping" ? (
          <path className="face" d="M29.4 20.2 h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        ) : state === "happy" ? (
          <>
            <circle className="face" cx="31.6" cy="19.6" r="1" fill="currentColor" stroke="none" />
            <path className="face" d="M29.6 21.4 q1.6 1.6 3.2 0" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </>
        ) : state === "searching" ? (
          <circle className="face" cx="31.4" cy="20.2" r="1.15" fill="currentColor" stroke="none" />
        ) : (
          <circle className="face" cx="32" cy="20" r="1.1" fill="currentColor" stroke="none" />
        )}
      </g>
      {state === "sleeping" && (
        <g className="ant-z" fill="currentColor" stroke="none">
          <text className="z z1" x="34" y="11" fontSize="7" fontWeight="700">z</text>
          <text className="z z2" x="38" y="6" fontSize="9" fontWeight="700">z</text>
        </g>
      )}
      {state === "working" && (
        <rect className="ant-load" x="2.5" y="17.5" width="7.5" height="7.5" rx="1.6" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="1.5" />
      )}
      {state === "happy" && (
        <g className="ant-spark" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
          <path className="sp s1" d="M7 12 v3 M5.5 13.5 h3" />
          <path className="sp s2" d="M38 22 v2.4 M36.8 23.2 h2.4" />
        </g>
      )}
      {state === "searching" && (
        <>
          <g className="ant-mag" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
            <circle cx="8" cy="13" r="4" fill="currentColor" fillOpacity=".12" />
            <path d="M11 16 l3 3" />
          </g>
          <text className="ant-q" x="33" y="11" fontSize="10" fontWeight="800" fill="currentColor" stroke="none">?</text>
        </>
      )}
    </svg>
  );
}
