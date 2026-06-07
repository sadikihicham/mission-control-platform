"use client";
// @ts-nocheck

// Robot.tsx — distinct robot avatars per hierarchical role.
// Monochrome line-art tinted by the agent's status colour (passed as `color`);
// the SILHOUETTE encodes the role. Each head shape, eye treatment and antenna
// emblem is unique.

// Map structural tree roles -> a business role used for the avatar.
const ROLE_ALIAS = { orchestrator: "director", lead: "engineer", worker: "developer" };

// Each entry returns the inner <g> of a 40×40 viewBox robot.
const BOTS = {
  // DIRECTOR — crowned pentagon head, diamond antenna, broad epaulettes. Commanding.
  director: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 8.4V4.6" />
      <path d="M20 2 l1.9 1.9 -1.9 1.9 -1.9 -1.9 z" fill="currentColor" stroke="none" />
      <path d="M11.5 15 V13 l3 1.8 2.7-4 2.8 4 2.7-4 2.8 4 3-1.8 V15" />
      <rect x="11.5" y="14.6" width="17" height="11.4" rx="4" fill="currentColor" fillOpacity=".08" />
      <circle cx="16" cy="20" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="24" cy="20" r="1.35" fill="currentColor" stroke="none" />
      <path d="M16.5 23.4h7" opacity=".5" />
      <path d="M7.5 34 Q7.5 28 13 27 H27 Q32.5 28 32.5 34" />
      <path d="M14 30.5h12" opacity=".45" />
    </g>
  ),
  // ENGINEER — hard-hat head with a gear crest, bolt cheeks, single visor bar.
  engineer: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="20" cy="6.4" r="2.2" />
      <path d="M20 4.2v-1.6M20 10.2v-1.6M22.5 6.4h1.6M15.9 6.4h1.6M21.8 4.6l1.1-1.1M17.1 9.3l1.1-1.1M21.8 8.2l1.1 1.1M17.1 3.5l1.1 1.1" opacity=".9" />
      <path d="M11 16.5a9 9 0 0 1 18 0" />
      <path d="M9.5 16.5h21" />
      <rect x="11.5" y="16.5" width="17" height="9.5" rx="4" fill="currentColor" fillOpacity=".08" />
      <rect x="15" y="20" width="10" height="2.6" rx="1.3" fill="currentColor" stroke="none" />
      <circle cx="11.8" cy="21" r="1" fill="currentColor" stroke="none" />
      <circle cx="28.2" cy="21" r="1" fill="currentColor" stroke="none" />
      <path d="M11 33 Q11 28 15 27.5 H25 Q29 28 29 33" />
    </g>
  ),
  // DEVELOPER — squircle head, < > bracket eyes, blinking-cursor antenna.
  developer: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 9V5.5" />
      <rect x="18.7" y="2.4" width="2.6" height="3.4" rx=".6" fill="currentColor" stroke="none" />
      <rect x="11" y="9" width="18" height="16" rx="6" fill="currentColor" fillOpacity=".08" />
      <path d="M17 15.5l-2.4 2.4 2.4 2.4" />
      <path d="M23 15.5l2.4 2.4-2.4 2.4" />
      <path d="M19 22.5h2.4" opacity=".55" />
      <path d="M10.5 33 Q10.5 28 15 27.3 H25 Q29.5 28 29.5 33" />
      <path d="M20 27.3V25" />
    </g>
  ),
  // DESIGNER — tilted round head, pen-nib antenna, mismatched circle+square eyes.
  designer: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 8.2l1.8-3.4" />
      <path d="M23.4 3l2.4 1.3-1.2 2.4-2.4-1.3z" fill="currentColor" fillOpacity=".25" />
      <path d="M24.6 6.7l-.9 1.7" />
      <circle cx="19.5" cy="17.5" r="8.6" fill="currentColor" fillOpacity=".08" />
      <circle cx="16.6" cy="17" r="1.5" fill="currentColor" stroke="none" />
      <rect x="21.2" y="15.6" width="3" height="3" rx=".7" fill="currentColor" stroke="none" />
      <path d="M16.5 21.2q3 2 6.4 0" opacity=".55" />
      <path d="M11 33.5 Q11 28.5 15.5 27.8 H24.5 Q29 28.5 29 33.5" />
      <circle cx="14.5" cy="30.6" r="1" fill="currentColor" stroke="none" opacity=".6" />
      <circle cx="20" cy="30.6" r="1" fill="currentColor" stroke="none" opacity=".6" />
      <circle cx="25.5" cy="30.6" r="1" fill="currentColor" stroke="none" opacity=".6" />
    </g>
  ),
  // ANALYST — visor showing a bar chart, a monocle over one eye, dot antenna.
  analyst: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 8.6V5" />
      <circle cx="20" cy="3.2" r="1.7" fill="currentColor" stroke="none" />
      <rect x="10.5" y="8.6" width="19" height="11.6" rx="3.4" fill="currentColor" fillOpacity=".08" />
      <path d="M14 17v-2.2M17.3 17v-4M20.6 17v-2.8M23.9 17v-5" />
      <circle cx="15.6" cy="24" r="2.4" />
      <path d="M17.3 25.7l1.4 1.4" />
      <circle cx="24" cy="24" r="1.2" fill="currentColor" stroke="none" />
      <path d="M11 34 Q11 29 15 28.4 H25 Q29 29 29 34" />
    </g>
  ),
  // TESTER — magnifier-eye head, checkmark antenna emblem.
  tester: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 8.6V5.4" />
      <path d="M17.6 3.4l1.7 1.7 3-3.2" />
      <rect x="11" y="8.8" width="18" height="11.8" rx="5.6" fill="currentColor" fillOpacity=".08" />
      <circle cx="17" cy="14.4" r="3" />
      <path d="M19.2 16.6l2 2" />
      <circle cx="24.4" cy="15" r="1.2" fill="currentColor" stroke="none" />
      <path d="M15.5 18.6h6" opacity=".5" />
      <path d="M11 33.5 Q11 28.5 15 27.9 H25 Q29 28.5 29 33.5" />
    </g>
  ),
  // SECURITY — shield-shaped head with a keyhole, two guard eyes.
  security: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 8.4V5" />
      <circle cx="20" cy="3.3" r="1.6" fill="currentColor" stroke="none" />
      <path d="M20 8.6c4 1.8 8 1.6 8 1.6 0 7-3.4 11.4-8 13.4-4.6-2-8-6.4-8-13.4 0 0 4 .2 8-1.6z" fill="currentColor" fillOpacity=".08" />
      <circle cx="20" cy="14.6" r="1.7" />
      <path d="M20 16.3V19" />
      <circle cx="15.8" cy="13.6" r=".9" fill="currentColor" stroke="none" opacity=".7" />
      <circle cx="24.2" cy="13.6" r=".9" fill="currentColor" stroke="none" opacity=".7" />
      <path d="M11.5 34 Q11.5 29.5 15.5 28.8 H24.5 Q28.5 29.5 28.5 34" />
    </g>
  ),
  // DATA — head built from stacked database cylinders, dotted readout eyes.
  data: (
    <g fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 8V4.6" />
      <path d="M16.6 4.6h6.8" />
      <ellipse cx="20" cy="11" rx="8.5" ry="2.8" fill="currentColor" fillOpacity=".08" />
      <path d="M11.5 11v8c0 1.6 3.8 2.8 8.5 2.8s8.5-1.2 8.5-2.8v-8" fill="currentColor" fillOpacity=".08" />
      <path d="M11.5 15c0 1.6 3.8 2.8 8.5 2.8s8.5-1.2 8.5-2.8" opacity=".55" />
      <circle cx="16.4" cy="19.2" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="23.6" cy="19.2" r="1.1" fill="currentColor" stroke="none" />
      <path d="M11 34 Q11 29.2 15 28.6 H25 Q29 29.2 29 34" />
    </g>
  ),
};

const ROLE_LABEL = {
  director: "Director",
  engineer: "Engineer",
  developer: "Developer",
  designer: "Designer",
  analyst: "Analyst",
  tester: "Tester",
  security: "Security",
  data: "Data",
};

function resolveRole(role) {
  if (!role) return "developer";
  if (ROLE_ALIAS[role]) return ROLE_ALIAS[role];
  return BOTS[role] ? role : "developer";
}

// infer what a working agent is *doing* from its current step / task text
export function robotActivityOf(agent) {
  const s = ((agent && (agent.step || "")) + " " + (agent && (agent.task || ""))).toLowerCase();
  if (/audit|secur|sécur|vulnér|vulner|scan|review|pull request|\bpr\b/.test(s)) return "auditing";
  if (/test|coverage|flaky|spec|regress|verify|vérif/.test(s)) return "testing";
  if (/plan|analy|map|cartograph|profil|strateg|stratég|design|réparti|reparti/.test(s)) return "thinking";
  return "coding";
}

// small accessory bubble shown above the robot head
const ACT_BUBBLE = (inner) => (
  <g className="robot-acc">
    <rect x="26.5" y="-1" width="14" height="12" rx="3.5" fill="currentColor" fillOpacity=".16" stroke="currentColor" strokeWidth="1" strokeOpacity=".3" />
    {inner}
  </g>
);
const ACTIVITY = {
  coding: ACT_BUBBLE(
    <g className="act act-coding" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M31.5 2.2 L29 5 l2.5 2.8" /><path d="M35.5 2.2 L38 5 l-2.5 2.8" />
    </g>
  ),
  thinking: ACT_BUBBLE(
    <g className="act act-thinking" fill="currentColor" stroke="none">
      <circle className="d d1" cx="30" cy="5" r="1.15" /><circle className="d d2" cx="33.5" cy="5" r="1.15" /><circle className="d d3" cx="37" cy="5" r="1.15" />
    </g>
  ),
  auditing: ACT_BUBBLE(
    <g className="act act-auditing" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="32.4" cy="4.2" r="2.4" fill="currentColor" fillOpacity=".18" /><path d="M34.3 6.1 l2.1 2.1" />
    </g>
  ),
  testing: ACT_BUBBLE(
    <g className="act act-testing" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M29.5 5 l2.2 2.2 4.3 -4.6" />
    </g>
  ),
};
const OVERLAY = {
  paused: (
    <g className="robot-ov ov-paused" fill="currentColor" stroke="none" fontFamily="var(--mono)" fontWeight="700">
      <text className="z z1" x="30" y="5" fontSize="6">z</text>
      <text className="z z2" x="34.5" y="0.5" fontSize="8">z</text>
    </g>
  ),
  queued: (
    <g className="robot-ov ov-queued" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <circle cx="34" cy="5" r="3.4" fill="currentColor" fillOpacity=".14" /><path d="M34 3 v2.2 l1.5 1" />
    </g>
  ),
  alert: (
    <g className="robot-ov ov-alert">
      <circle cx="34" cy="5" r="4" fill="currentColor" /><rect x="33.2" y="2.6" width="1.6" height="3" rx=".8" fill="#fff" /><circle cx="34" cy="7" r=".9" fill="#fff" />
    </g>
  ),
  done: (
    <g className="robot-ov ov-done">
      <circle cx="34" cy="4.5" r="4.2" fill="currentColor" /><path d="M31.9 4.6 l1.5 1.5 2.8 -3" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path className="spk" d="M27 9 v2 M26 10 h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </g>
  ),
};

export function Robot({ role, color = "currentColor", size = 40, status, activity, paused, style }) {
  const r = resolveRole(role);
  let st = null;
  if (status) {
    st = paused ? "paused" : status === "running" ? "working"
      : status === "waiting" ? "queued" : status === "blocked" ? "alert"
      : status === "done" ? "done" : null;
  }
  const act = st === "working" ? (activity || "coding") : null;
  const cls = "robot" + (st ? " robot-" + st : "") + (act ? " robot-live act-" + act : "") + (st === "done" ? " robot-live" : "");
  return (
    <svg className={cls} width={size} height={size}
      viewBox="0 0 40 40" style={{ color, display: "block", overflow: "visible", ...(style || {}) }} aria-hidden="true">
      <g className="robot-figure">{BOTS[r]}</g>
      {act && ACTIVITY[act]}
      {st && st !== "working" && OVERLAY[st]}
    </svg>
  );
}

export function robotRoleLabel(role) {
  const r = resolveRole(role);
  return ROLE_LABEL[r] || ROLE_LABEL.developer;
}
