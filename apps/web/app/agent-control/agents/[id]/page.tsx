"use client";

import { useParams } from "next/navigation";

import { AgentDetail } from "@/components/agent-control/AgentDetail";
import { AcGuard } from "@/components/agent-control/States";

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  return (
    <AcGuard cap="view">
      <AgentDetail agentId={id} />
    </AcGuard>
  );
}
