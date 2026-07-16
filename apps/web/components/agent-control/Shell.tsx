"use client";

// Shell local du module — n'apparaît QU'EN mode standalone (SP5 §15). En mode
// embedded, l'hôte fournit topbar/sidebar/profil/langue/logout : on ne les
// duplique jamais. Ici, seule la navigation interne du module est rendue.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { acRequest } from "@/lib/agent-control/client";
import { useAgentControl } from "@/lib/agent-control/provider";
import type { HealthOut } from "@/lib/contracts";

const TABS: { seg: string; key: string }[] = [
  { seg: "", key: "nav_dashboard" },
  { seg: "agents", key: "nav_agents" },
  { seg: "projects", key: "nav_projects" },
  { seg: "runs", key: "nav_runs" },
  { seg: "approvals", key: "nav_approvals" },
  { seg: "alerts", key: "nav_alerts" },
  { seg: "costs", key: "nav_costs" },
  { seg: "audit", key: "nav_audit" },
  { seg: "settings", key: "nav_settings" },
];

export function AcShell({ children }: { children: ReactNode }) {
  const { embedded, basePath, t, rtl } = useAgentControl();
  const pathname = usePathname();

  const content = <div className="mx-auto max-w-5xl px-4 py-6">{children}</div>;
  if (embedded) return content; // pas de shell dupliqué en embedded

  return (
    <div dir={rtl ? "rtl" : "ltr"} className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800">
        <div className="mx-auto max-w-5xl px-4 py-3">
          <div className="mb-3 text-sm font-semibold tracking-wide text-neutral-300">
            Agent Control
          </div>
          <nav className="flex flex-wrap gap-1 text-sm" aria-label="Agent Control">
            {TABS.map((tab) => {
              const href = tab.seg ? `${basePath}/${tab.seg}` : basePath;
              const active =
                tab.seg === ""
                  ? pathname === basePath
                  : pathname.startsWith(`${basePath}/${tab.seg}`);
              return (
                <Link
                  key={tab.seg || "root"}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 ${
                    active ? "bg-neutral-800 text-white" : "text-neutral-400 hover:bg-neutral-900"
                  }`}
                >
                  {t(tab.key)}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      {content}
    </div>
  );
}

export function Settings() {
  const { t, locale, installationId, capabilities, embedded } = useAgentControl();
  const health = useQuery<HealthOut>({
    queryKey: ["ac", installationId ?? "local", "health"],
    queryFn: ({ signal }) => acRequest<HealthOut>("/health", { signal }),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-100">{t("nav_settings")}</h2>
      <dl className="grid gap-2 rounded-xl border border-neutral-800 p-4 text-sm">
        <Row label="installation" value={installationId ?? "—"} />
        <Row label="locale" value={locale} />
        <Row label="mode" value={embedded ? "embedded" : "standalone"} />
        <Row
          label={t("capabilities")}
          value={[...capabilities].join(", ") || "—"}
        />
        <Row
          label={t("health")}
          value={
            health.isLoading
              ? t("loading")
              : health.data
                ? `${health.data.status} · ${health.data.installation_status}`
                : "—"
          }
        />
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-neutral-800/60 py-1.5">
      <dt className="text-neutral-400">{label}</dt>
      <dd className="truncate text-neutral-200">{value}</dd>
    </div>
  );
}
