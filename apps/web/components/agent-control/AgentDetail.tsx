"use client";

// Détail d'un agent (SP5 §10) : métadonnées, capacités, santé, credentials
// (secret affiché une seule fois, jamais conservé), cycle de vie.
import { useState } from "react";

import {
  useAgent,
  useAgentHealth,
  useAgentLifecycle,
  useCreateCredential,
} from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { useAcTopic } from "@/lib/agent-control/realtime";
import { AcError, AcLoading } from "./States";

export function AgentDetail({ agentId }: { agentId: string }) {
  const ac = useAgentControl();
  const { t, can } = ac;
  // Temps réel : souscrit au topic de cet agent le temps du détail (P9, gap 1).
  useAcTopic(ac, agentId ? `agent:${agentId}` : null);
  const q = useAgent(agentId);
  const health = useAgentHealth(agentId);
  const lifecycle = useAgentLifecycle(agentId);

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  const a = q.data;
  if (!a) return <AcLoading />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">{a.display_name ?? a.agent_key}</h2>
        <p className="text-xs text-neutral-500">{a.agent_key}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Info label={t("status")} value={a.status} />
        <Info label={t("state")} value={a.state} />
        <Info label="runtime" value={a.runtime ?? "—"} />
        <Info label="provider" value={a.provider ?? "—"} />
        <Info label="environment" value={a.environment ?? "—"} />
        <Info label={t("last_heartbeat")} value={a.last_heartbeat ?? "—"} />
      </div>

      <section>
        <h3 className="mb-2 text-sm font-medium text-neutral-300">{t("capabilities")}</h3>
        <div className="flex flex-wrap gap-1.5">
          {(a.capabilities ?? []).length === 0 ? (
            <span className="text-xs text-neutral-500">—</span>
          ) : (
            a.capabilities.map((c) => (
              <span key={c} className="rounded border border-neutral-700 px-1.5 py-0.5 text-xs text-neutral-300">
                {c}
              </span>
            ))
          )}
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-medium text-neutral-300">{t("health")}</h3>
        {health.isLoading ? (
          <AcLoading />
        ) : health.isError ? (
          <AcError error={health.error} onRetry={() => void health.refetch()} />
        ) : health.data ? (
          <div className="flex items-center gap-3 text-sm">
            <span className={health.data.healthy ? "text-emerald-400" : "text-amber-400"}>
              {health.data.healthy ? t("healthy") : t("unhealthy")}
            </span>
            <span className="text-neutral-500">
              {health.data.active_runs} {t("runs").toLowerCase()} · {health.data.open_alerts} {t("nav_alerts").toLowerCase()}
            </span>
          </div>
        ) : null}
      </section>

      {can("manage_agents") && (
        <>
          <CredentialSection agentId={agentId} />
          <section className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => lifecycle.mutate("suspend")}
              className="rounded-md border border-amber-700 px-3 py-1.5 text-sm text-amber-300"
            >
              {t("suspend")}
            </button>
            <button
              type="button"
              onClick={() => lifecycle.mutate("resume")}
              className="rounded-md border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300"
            >
              {t("resume")}
            </button>
            <button
              type="button"
              onClick={() => lifecycle.mutate("archive")}
              className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300"
            >
              {t("archive")}
            </button>
          </section>
        </>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 p-3">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="mt-0.5 truncate text-sm text-neutral-200">{value}</div>
    </div>
  );
}

function CredentialSection({ agentId }: { agentId: string }) {
  const { t } = useAgentControl();
  const m = useCreateCredential(agentId);
  const [copied, setCopied] = useState(false);
  const secret = m.data?.secret ?? null;

  return (
    <section>
      <h3 className="mb-2 text-sm font-medium text-neutral-300">{t("credentials")}</h3>
      {secret ? (
        <div className="space-y-2 rounded-lg border border-emerald-800 bg-emerald-950/30 p-3">
          <div className="text-xs text-emerald-300">{t("secret_once")}</div>
          <code className="block break-all rounded bg-neutral-950 p-2 text-xs text-neutral-100">
            {secret}
          </code>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(secret);
              setCopied(true);
            }}
            className="rounded-md border border-neutral-700 px-2 py-1 text-xs text-neutral-200"
          >
            {copied ? t("copied") : t("copy")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => m.mutate({ scopes: ["ingest"] } as never)}
          disabled={m.isPending}
          className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm text-neutral-100 disabled:opacity-50"
        >
          {t("new_credential")}
        </button>
      )}
    </section>
  );
}
