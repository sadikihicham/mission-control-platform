// Helpers du design Claude adaptés à nos états (idle|working|blocked|done|error|stale).
import type { Agent } from "@/lib/api";

export type McStatusKey = "working" | "idle" | "stale" | "blocked" | "error" | "done";

export const STATUS: Record<string, { clr: string; badge: string; label: string }> = {
  working: { clr: "var(--run)", badge: "st-running", label: "working" },
  idle: { clr: "var(--tx-lo)", badge: "st-waiting", label: "idle" },
  stale: { clr: "var(--wait)", badge: "st-waiting", label: "stale" },
  blocked: { clr: "var(--block)", badge: "st-blocked", label: "blocked" },
  error: { clr: "var(--block)", badge: "st-blocked", label: "error" },
  done: { clr: "var(--done)", badge: "st-done", label: "done" },
};

export const statusOf = (s: string) => STATUS[s] ?? STATUS.idle;

// Buckets pour la barre de santé segmentée (4 familles du design).
export type HealthCounts = { running: number; waiting: number; blocked: number; done: number };

export const HEALTH_META: Record<keyof HealthCounts, { clr: string; label: string }> = {
  blocked: { clr: "var(--block)", label: "bloqués" },
  running: { clr: "var(--run)", label: "actifs" },
  waiting: { clr: "var(--wait)", label: "en attente" },
  done: { clr: "var(--done)", label: "terminés" },
};
export const HEALTH_ORDER: (keyof HealthCounts)[] = ["blocked", "running", "waiting", "done"];

export function bucketOf(state: string): keyof HealthCounts {
  if (state === "blocked" || state === "error") return "blocked";
  if (state === "working") return "running";
  if (state === "done") return "done";
  return "waiting"; // idle, stale
}

export function healthFrom(agents: { state: string }[]): HealthCounts {
  const c: HealthCounts = { running: 0, waiting: 0, blocked: 0, done: 0 };
  agents.forEach((a) => {
    c[bucketOf(a.state)] += 1;
  });
  return c;
}

// Dégradé rouge → ambre → vert selon le taux de complétion (0..1).
export function completionColor(ratio: number): string {
  const t = Math.max(0, Math.min(1, ratio));
  const hue = 4 + (142 - 4) * t;
  const sat = 70 - 8 * Math.sin(Math.PI * t);
  return `hsl(${hue.toFixed(0)} ${sat.toFixed(0)}% 56%)`;
}

// Formatters (durée à partir d'âge en secondes).
export const fmtAge = (sec: number | null): string => {
  if (sec == null) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}min`;
  return `${Math.round(sec / 3600)}h`;
};

export const monogram = (name: string): string =>
  name
    .replace(/[^a-zA-Z0-9 ]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || "PR";

export const agentKey = (a: Agent) => a.agent;
