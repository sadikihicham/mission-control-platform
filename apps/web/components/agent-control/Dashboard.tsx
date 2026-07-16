"use client";

// Écran tableau de bord (SP5 §9) : santé, runs, validations, budget — 100 % API.
import { useDashboard } from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { AcError, AcLoading } from "./States";

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
      <div className="text-xs text-neutral-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${tone ?? "text-neutral-100"}`}>{value}</div>
    </div>
  );
}

export function Dashboard() {
  const { t } = useAgentControl();
  const q = useDashboard();

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  const d = q.data;
  if (!d) return <AcLoading />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t("agents_total")} value={d.agents.total} />
        <Stat label={t("active")} value={d.agents.active} tone="text-emerald-400" />
        <Stat label={t("runs")} value={d.runs.total} />
        <Stat label={t("approvals_pending")} value={d.approvals_pending} tone="text-amber-400" />
        <Stat label={t("alerts_open")} value={d.alerts_open} tone="text-red-400" />
        <Stat label={t("total_cost")} value={`${d.cost.total_cost} ${d.cost.currency}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-neutral-800 p-4">
          <div className="mb-3 text-sm font-medium text-neutral-200">{t("nav_agents")}</div>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <Row label={t("active")} value={d.agents.working + d.agents.idle} />
            <Row label="stale" value={d.agents.stale} />
            <Row label="blocked" value={d.agents.blocked} />
            <Row label="error" value={d.agents.error} />
            <Row label="suspended" value={d.agents.suspended} />
            <Row label="archived" value={d.agents.archived} />
          </dl>
        </div>
        <div className="rounded-xl border border-neutral-800 p-4">
          <div className="mb-3 text-sm font-medium text-neutral-200">{t("nav_runs")}</div>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <Row label="running" value={d.runs.running} />
            <Row label="waiting_approval" value={d.runs.waiting_approval} />
            <Row label="blocked" value={d.runs.blocked} />
            <Row label="succeeded" value={d.runs.succeeded} />
            <Row label="failed" value={d.runs.failed} />
            <Row label="timed_out" value={d.runs.timed_out} />
          </dl>
        </div>
      </div>

      <div className="rounded-xl border border-neutral-800 p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="text-neutral-300">{t("progress")}</span>
          <span className="text-neutral-400">{d.overall_progress}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-800">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, d.overall_progress))}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between border-b border-neutral-800/60 py-1">
      <dt className="text-neutral-400">{label}</dt>
      <dd className="text-neutral-200">{value}</dd>
    </div>
  );
}
