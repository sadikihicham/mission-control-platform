"use client";

import { Costs } from "@/components/agent-control/Operations";
import { AcGuard } from "@/components/agent-control/States";

export default function CostsPage() {
  return (
    <AcGuard cap="view_costs">
      <Costs />
    </AcGuard>
  );
}
