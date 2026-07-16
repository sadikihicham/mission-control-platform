"use client";

import { Audit } from "@/components/agent-control/Operations";
import { AcGuard } from "@/components/agent-control/States";

export default function AuditPage() {
  return (
    <AcGuard cap="view">
      <Audit />
    </AcGuard>
  );
}
