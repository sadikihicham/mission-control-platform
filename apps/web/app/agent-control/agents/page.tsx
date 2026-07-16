"use client";

import { useRouter } from "next/navigation";

import { Agents } from "@/components/agent-control/Agents";
import { AcGuard } from "@/components/agent-control/States";
import { useAgentControl } from "@/lib/agent-control/provider";

export default function AgentsPage() {
  const router = useRouter();
  const { basePath } = useAgentControl();
  return (
    <AcGuard cap="view">
      <Agents onOpen={(id) => router.push(`${basePath}/agents/${id}`)} />
    </AcGuard>
  );
}
