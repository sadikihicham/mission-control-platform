"use client";

import { Approvals } from "@/components/agent-control/Approvals";
import { AcGuard } from "@/components/agent-control/States";

export default function ApprovalsPage() {
  return (
    <AcGuard cap="view">
      <Approvals />
    </AcGuard>
  );
}
