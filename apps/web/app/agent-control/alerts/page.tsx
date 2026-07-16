"use client";

import { Alerts } from "@/components/agent-control/Operations";
import { AcGuard } from "@/components/agent-control/States";

export default function AlertsPage() {
  return (
    <AcGuard cap="view">
      <Alerts />
    </AcGuard>
  );
}
