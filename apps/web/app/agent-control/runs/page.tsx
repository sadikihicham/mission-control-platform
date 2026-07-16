"use client";

import { useRouter } from "next/navigation";

import { Runs } from "@/components/agent-control/Runs";
import { AcGuard } from "@/components/agent-control/States";
import { useAgentControl } from "@/lib/agent-control/provider";

export default function RunsPage() {
  const router = useRouter();
  const { basePath } = useAgentControl();
  return (
    <AcGuard cap="view">
      <Runs onOpen={(id) => router.push(`${basePath}/runs/${id}`)} />
    </AcGuard>
  );
}
