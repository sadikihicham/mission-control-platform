"use client";

export type Toast = { id: number; kind: "stale" | "blocked" | "error"; text: string };

const KIND = {
  stale: { dot: "bg-agent-stale", label: "STALE" },
  blocked: { dot: "bg-agent-blocked", label: "BLOQUÉ" },
  error: { dot: "bg-agent-error", label: "ERREUR" },
};

export function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const k = KIND[t.kind];
        return (
          <div
            key={t.id}
            className="pointer-events-auto flex items-start gap-2 rounded-xl border border-neutral-700 bg-neutral-900 px-3 py-2 shadow-lg"
          >
            <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${k.dot}`} />
            <div className="text-sm">
              <div className="text-[10px] font-semibold tracking-wider text-neutral-400">{k.label}</div>
              <div className="text-neutral-200">{t.text}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
