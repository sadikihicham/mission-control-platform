"use client";

// Écrans opérationnels (SP5 §8) : alertes (ack/resolve), coûts (usage réel),
// audit (redacted côté serveur — on n'affiche jamais de brut sensible ici).
import { useState } from "react";

import { acDownload, AcApiError } from "@/lib/agent-control/client";
import { useAlertAction, useAlerts, useAudit, useUsage } from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { AcEmpty, AcError, AcLoading } from "./States";

const SEV_TONE: Record<string, string> = {
  info: "text-sky-400",
  warning: "text-amber-400",
  critical: "text-red-400",
};

export function Alerts() {
  const { t, can } = useAgentControl();
  const q = useAlerts();

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data || q.data.items.length === 0) return <AcEmpty />;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-100">{t("nav_alerts")}</h2>
      <ul className="space-y-2">
        {q.data.items.map((a) => (
          <li key={a.id} className="flex items-center justify-between rounded-lg border border-neutral-800 p-3">
            <div className="min-w-0">
              <div className="truncate text-sm text-neutral-100">{a.title}</div>
              <div className="text-xs text-neutral-500">
                <span className={SEV_TONE[a.severity] ?? "text-neutral-400"}>{a.severity}</span> · {a.status} · {a.opened_at}
              </div>
            </div>
            {can("operate") && a.status !== "resolved" && <AlertActions alertId={a.id} status={a.status} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AlertActions({ alertId, status }: { alertId: string; status: string }) {
  const { t } = useAgentControl();
  const m = useAlertAction(alertId);
  return (
    <div className="flex gap-2">
      {status === "open" && (
        <button
          type="button"
          onClick={() => m.mutate("acknowledge")}
          className="rounded-md border border-neutral-700 px-2 py-1 text-xs text-neutral-200"
        >
          {t("acknowledge")}
        </button>
      )}
      <button
        type="button"
        onClick={() => m.mutate("resolve")}
        className="rounded-md border border-emerald-700 px-2 py-1 text-xs text-emerald-300"
      >
        {t("resolve")}
      </button>
    </div>
  );
}

export function Costs() {
  const { t, can, installationId } = useAgentControl();
  const q = useUsage();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function onExport() {
    setExporting(true);
    setExportError(null);
    try {
      await acDownload("/reports/export.csv", "agent-control-usage.csv", { installationId });
    } catch (e) {
      setExportError(e instanceof AcApiError ? e.message : String(e));
    } finally {
      setExporting(false);
    }
  }

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  const d = q.data;
  if (!d) return <AcEmpty />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-100">{t("nav_costs")}</h2>
        {can("view_costs") && (
          <button
            type="button"
            onClick={() => void onExport()}
            disabled={exporting}
            className="rounded-lg border border-neutral-700 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-50"
          >
            {exporting ? t("exporting") : t("export_csv")}
          </button>
        )}
      </div>
      {exportError && <p className="text-sm text-red-400">{exportError}</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label={t("total_cost")} value={`${d.summary.total_cost} ${d.summary.currency}`} />
        <Kpi label="tokens" value={d.summary.total_tokens} />
        <Kpi label="calls" value={d.summary.total_calls} />
        <Kpi label="records" value={d.summary.record_count} />
      </div>
      {d.items.length === 0 ? (
        <AcEmpty />
      ) : (
        <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800 text-sm">
          {d.items.map((u) => (
            <li key={u.id} className="flex items-center justify-between px-4 py-2">
              <span className="truncate text-neutral-300">{u.model ?? u.provider ?? u.agent_id}</span>
              <span className="text-neutral-400">
                {u.cost} {u.currency}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-neutral-800 p-4">
      <div className="text-xs text-neutral-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-neutral-100">{value}</div>
    </div>
  );
}

export function Audit() {
  const { t } = useAgentControl();
  const q = useAudit();

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data || q.data.items.length === 0) return <AcEmpty />;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-100">{t("nav_audit")}</h2>
      <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800 text-sm">
        {q.data.items.map((e) => (
          <li key={e.id} className="flex items-center justify-between px-4 py-2">
            <span className="min-w-0">
              <span className="block truncate text-neutral-200">{e.action}</span>
              <span className="block truncate text-xs text-neutral-500">
                {e.actor_type}
                {e.actor_label ? ` · ${e.actor_label}` : ""}
                {e.target_type ? ` → ${e.target_type}` : ""}
              </span>
            </span>
            <span className="whitespace-nowrap text-xs text-neutral-600">{e.created_at}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
