import type { AgentState } from "@/lib/api";

export const STATE: Record<string, { dot: string; text: string; label: string }> = {
  working: { dot: "bg-agent-working", text: "text-agent-working", label: "WORKING" },
  blocked: { dot: "bg-agent-blocked", text: "text-agent-blocked", label: "BLOCKED" },
  stale: { dot: "bg-agent-stale", text: "text-agent-stale", label: "STALE" },
  error: { dot: "bg-agent-error", text: "text-agent-error", label: "ERROR" },
  done: { dot: "bg-agent-done", text: "text-agent-done", label: "DONE" },
  idle: { dot: "bg-agent-idle", text: "text-agent-idle", label: "IDLE" },
};

export function st(s: string) {
  return STATE[s] ?? STATE.idle;
}

export function StateBadge({ state }: { state: AgentState | string }) {
  const s = st(state);
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold tracking-wider ${s.text}`}>
      <span className={`h-2 w-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

// Couleur selon le taux de réalisation : 0% rouge → 50% jaune → 100% vert.
// Projet terminé (status done ou 100%) → vert plein.
export function progressColor(progress: number, status?: string): string {
  if (status === "done" || status === "archived" || progress >= 100) return "hsl(142 71% 45%)";
  const hue = Math.max(0, Math.min(130, Math.round((progress / 100) * 130)));
  return `hsl(${hue} 75% 48%)`;
}

export function Bar({
  progress,
  state,
  byProgress,
  status,
}: {
  progress: number;
  state?: string;
  byProgress?: boolean;
  status?: string;
}) {
  const s = st(state ?? (progress >= 100 ? "done" : progress > 0 ? "working" : "idle"));
  const style = byProgress
    ? { width: `${progress}%`, backgroundColor: progressColor(progress, status) }
    : { width: `${progress}%` };
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-800">
      <div className={`h-full transition-all ${byProgress ? "" : s.dot}`} style={style} />
    </div>
  );
}

export function ago(sec: number | null): string {
  if (sec == null) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}min`;
  return `${Math.round(sec / 3600)}h`;
}
