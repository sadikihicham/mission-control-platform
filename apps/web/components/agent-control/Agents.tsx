"use client";

// Écran flotte d'agents (SP5 §8/§10) : liste API + enregistrement (manage_agents).
import { useState } from "react";

import { useAgents, useRegisterAgent } from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { AcApiError } from "@/lib/agent-control/client";
import { AcEmpty, AcError, AcLoading } from "./States";

const STATE_TONE: Record<string, string> = {
  working: "text-emerald-400",
  idle: "text-neutral-300",
  blocked: "text-amber-400",
  stale: "text-neutral-500",
  error: "text-red-400",
  done: "text-sky-400",
};

export function Agents({ onOpen }: { onOpen: (id: string) => void }) {
  const { t, can } = useAgentControl();
  const q = useAgents();
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-100">{t("nav_agents")}</h2>
        {can("manage_agents") && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500"
          >
            {t("register_agent")}
          </button>
        )}
      </div>

      {open && can("manage_agents") && <RegisterForm onDone={() => setOpen(false)} />}

      {q.isLoading ? (
        <AcLoading />
      ) : q.isError ? (
        <AcError error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data || q.data.items.length === 0 ? (
        <AcEmpty />
      ) : (
        <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800">
          {q.data.items.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => onOpen(a.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-start hover:bg-neutral-900"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm text-neutral-100">
                    {a.display_name ?? a.agent_key}
                  </span>
                  <span className="block truncate text-xs text-neutral-500">{a.agent_key}</span>
                </span>
                <span className="flex items-center gap-3 text-xs">
                  <span className={STATE_TONE[a.state] ?? "text-neutral-400"}>{a.state}</span>
                  <span className="rounded border border-neutral-700 px-1.5 py-0.5 text-neutral-400">
                    {a.status}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RegisterForm({ onDone }: { onDone: () => void }) {
  const { t } = useAgentControl();
  const m = useRegisterAgent();
  const [localKey, setLocalKey] = useState("");
  const [displayName, setDisplayName] = useState("");

  const err = m.error instanceof AcApiError ? m.error.message : null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate(
          { local_key: localKey, display_name: displayName || null } as never,
          { onSuccess: onDone },
        );
      }}
      className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-neutral-400">{t("local_key")}</span>
          <input
            required
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-neutral-400">{t("display_name")}</span>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
          />
        </label>
      </div>
      {err && <div className="text-xs text-red-400" role="alert">{err}</div>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={m.isPending}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {t("create")}
        </button>
        <button type="button" onClick={onDone} className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300">
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}
