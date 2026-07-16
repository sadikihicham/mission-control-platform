"use client";

// Écrans exécutions (SP5 §12) : liste paginée + détail avec timeline paginée.
import { useRun, useRunTimeline, useRuns } from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { useAcTopic } from "@/lib/agent-control/realtime";
import { AcEmpty, AcError, AcLoading } from "./States";

const RUN_TONE: Record<string, string> = {
  running: "text-emerald-400",
  succeeded: "text-sky-400",
  failed: "text-red-400",
  waiting_approval: "text-amber-400",
  blocked: "text-amber-400",
  timed_out: "text-red-400",
  cancelled: "text-neutral-500",
};

export function Runs({ onOpen }: { onOpen: (id: string) => void }) {
  const { t } = useAgentControl();
  const q = useRuns();

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data || q.data.items.length === 0) return <AcEmpty />;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-100">{t("nav_runs")}</h2>
      <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800">
        {q.data.items.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              onClick={() => onOpen(r.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-start hover:bg-neutral-900"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm text-neutral-100">
                  {r.objective ?? r.id}
                </span>
                <span className="block truncate text-xs text-neutral-500">{r.created_at}</span>
              </span>
              <span className={`text-xs ${RUN_TONE[r.state] ?? "text-neutral-400"}`}>{r.state}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RunDetail({ runId }: { runId: string }) {
  const ac = useAgentControl();
  const { t } = ac;
  // Temps réel : souscrit au topic de ce run le temps du détail (P9, gap 1).
  useAcTopic(ac, runId ? `run:${runId}` : null);
  const q = useRun(runId);
  const tl = useRunTimeline(runId);

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  const r = q.data;
  if (!r) return <AcLoading />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">{r.objective ?? r.id}</h2>
        <p className="text-xs text-neutral-500">
          <span className={RUN_TONE[r.state] ?? "text-neutral-400"}>{r.state}</span> · {r.id}
        </p>
      </div>

      <section>
        <h3 className="mb-2 text-sm font-medium text-neutral-300">{t("timeline")}</h3>
        {tl.isLoading ? (
          <AcLoading />
        ) : tl.isError ? (
          <AcError error={tl.error} onRetry={() => void tl.refetch()} />
        ) : !tl.data || tl.data.items.length === 0 ? (
          <AcEmpty />
        ) : (
          <ol className="space-y-1.5">
            {tl.data.items.map((ev) => (
              <li key={`${ev.sequence}-${ev.event_id}`} className="flex items-start gap-2 text-xs">
                <span className="mt-0.5 min-w-[3rem] text-neutral-500">#{ev.sequence}</span>
                <span className="text-neutral-300">{ev.event_type}</span>
                <span className="ms-auto text-neutral-600">{ev.occurred_at}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
