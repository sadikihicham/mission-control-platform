"use client";

import { useParams } from "next/navigation";

import { ProjectDetail } from "@/components/agent-control/Projects";
import { AcGuard } from "@/components/agent-control/States";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  return (
    <AcGuard cap="view">
      <ProjectDetail projectId={id} />
    </AcGuard>
  );
}
