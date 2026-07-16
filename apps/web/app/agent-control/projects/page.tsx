"use client";

import { useRouter } from "next/navigation";

import { Projects } from "@/components/agent-control/Projects";
import { AcGuard } from "@/components/agent-control/States";
import { useAgentControl } from "@/lib/agent-control/provider";

export default function ProjectsPage() {
  const router = useRouter();
  const { basePath } = useAgentControl();
  return (
    <AcGuard cap="view">
      <Projects onOpen={(id) => router.push(`${basePath}/projects/${id}`)} />
    </AcGuard>
  );
}
