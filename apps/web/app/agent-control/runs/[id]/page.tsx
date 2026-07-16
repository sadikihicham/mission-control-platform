"use client";

import { useParams } from "next/navigation";

import { RunDetail } from "@/components/agent-control/Runs";
import { AcGuard } from "@/components/agent-control/States";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  return (
    <AcGuard cap="view">
      <RunDetail runId={id} />
    </AcGuard>
  );
}
