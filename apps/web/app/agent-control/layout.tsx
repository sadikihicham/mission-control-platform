"use client";

// Point de montage standalone du module Agent Control (dev/autonome).
//
// L'hôte réel monterait plutôt `<AgentControlProvider embedded locale=… …>`
// autour de ses propres routes ; ici, l'adaptateur local résout le contexte via
// `/agent-control/v1/context` (réutilise le JWT hôte existant) et le shell local
// n'apparaît qu'en standalone (SP5 §15).
import type { ReactNode } from "react";

import { AgentControlProvider } from "@/lib/agent-control/provider";
import { AcShell } from "@/components/agent-control/Shell";

export default function AgentControlLayout({ children }: { children: ReactNode }) {
  return (
    <AgentControlProvider basePath="/agent-control">
      <AcShell>{children}</AcShell>
    </AgentControlProvider>
  );
}
