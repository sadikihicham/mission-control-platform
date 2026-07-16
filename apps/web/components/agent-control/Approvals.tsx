"use client";

// Écran approbations (SP5 §13) : contexte, impact, expiration, approve/reject
// avec confirmation explicite. La décision est vérifiée serveur (version optimiste).
import { useState } from "react";

import { useApprovalDecision, useApprovals } from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import type { ApprovalOut } from "@/lib/contracts";
import { AcEmpty, AcError, AcLoading } from "./States";

const RISK_TONE: Record<string, string> = {
  low: "text-neutral-400",
  medium: "text-amber-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export function Approvals() {
  const { t } = useAgentControl();
  const q = useApprovals("pending");

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data || q.data.items.length === 0) return <AcEmpty />;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-100">{t("nav_approvals")}</h2>
      <ul className="space-y-3">
        {q.data.items.map((a) => (
          <ApprovalCard key={a.id} approval={a} />
        ))}
      </ul>
    </div>
  );
}

function ApprovalCard({ approval }: { approval: ApprovalOut }) {
  const { t, can } = useAgentControl();
  const decision = useApprovalDecision(approval.id);
  const [comment, setComment] = useState("");

  const act = (kind: "approve" | "reject") => {
    const msg = kind === "approve" ? t("approve_confirm") : t("reject_confirm");
    if (typeof window !== "undefined" && !window.confirm(msg)) return;
    decision.mutate({ decision: kind, comment: comment || undefined });
  };

  return (
    <li className="rounded-xl border border-neutral-800 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-neutral-100">{approval.title}</div>
          <div className="mt-0.5 text-xs text-neutral-500">
            {approval.action_type} · {t("risk")}:{" "}
            <span className={RISK_TONE[approval.risk_level] ?? "text-neutral-400"}>
              {approval.risk_level}
            </span>
          </div>
        </div>
        {approval.expires_at && (
          <div className="whitespace-nowrap text-xs text-neutral-500">
            {t("expires")}: {approval.expires_at}
          </div>
        )}
      </div>

      {can("approve") && (
        <div className="mt-3 space-y-2">
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t("comment")}
            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-sm text-neutral-100"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={decision.isPending}
              onClick={() => act("approve")}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {t("approve")}
            </button>
            <button
              type="button"
              disabled={decision.isPending}
              onClick={() => act("reject")}
              className="rounded-md border border-red-700 px-3 py-1.5 text-sm text-red-300 disabled:opacity-50"
            >
              {t("reject")}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
