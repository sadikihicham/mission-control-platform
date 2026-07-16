"use client";

// États transverses des écrans (SP5 §14) : loading / empty / erreur typée
// (401/403/404/offline/générique) avec action de reprise. Aucun HTML/log brut
// non assaini n'est rendu : on n'affiche que des messages i18n + un code stable.
import { AcApiError } from "@/lib/agent-control/client";
import { useAgentControl } from "@/lib/agent-control/provider";

export function AcLoading() {
  const { t } = useAgentControl();
  return (
    <div className="flex items-center justify-center p-10 text-sm text-neutral-400" role="status" aria-live="polite">
      <span className="me-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-neutral-500 border-t-transparent" />
      {t("loading")}
    </div>
  );
}

export function AcEmpty({ label }: { label?: string }) {
  const { t } = useAgentControl();
  return (
    <div className="p-10 text-center text-sm text-neutral-400">{label ?? t("empty")}</div>
  );
}

export function AcError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useAgentControl();
  let title = t("error_title");
  let hint: string | null = null;
  let showRetry = true;

  if (error instanceof AcApiError) {
    if (error.isForbidden) {
      title = t("forbidden");
      hint = t("forbidden_hint");
      showRetry = false;
    } else if (error.isNotFound) {
      title = t("not_found");
      showRetry = false;
    } else if (error.isAuth) {
      title = t("unauthenticated");
      showRetry = false;
    } else if (error.isOffline) {
      title = t("offline");
    } else {
      hint = error.message;
    }
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 p-10 text-center" role="alert">
      <div className="text-sm font-medium text-red-400">{title}</div>
      {hint && <div className="max-w-md text-xs text-neutral-400">{hint}</div>}
      {showRetry && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-neutral-600 px-3 py-1.5 text-xs text-neutral-200 hover:bg-neutral-800"
        >
          {t("retry")}
        </button>
      )}
    </div>
  );
}

/** Garde de capacité côté UI (masquage). L'API vérifie toujours (SP5 §14). */
export function AcGuard({
  cap,
  children,
}: {
  cap: import("@/lib/contracts").Capability;
  children: React.ReactNode;
}) {
  const { can, t } = useAgentControl();
  if (!can(cap)) {
    return (
      <div className="p-10 text-center text-sm text-neutral-400" role="note">
        {t("forbidden")} — {t("forbidden_hint")}
      </div>
    );
  }
  return <>{children}</>;
}
