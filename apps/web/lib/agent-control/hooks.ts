"use client";

// Hooks React Query du module Agent Control — cache, mutations, invalidation
// ciblée (SP5 §5). Une clé par ressource/tenant : jamais deux pollings
// concurrents sur la même ressource. Toutes les lectures passent par le client
// HTTP unique (erreurs typées, abort géré par React Query via `signal`).
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { acRequest } from "./client";
import { useAgentControl } from "./provider";
import type {
  AcProjectCreate,
  AcProjectListOut,
  AcProjectOut,
  AcProjectUpdate,
  AcTaskAssign,
  AcTaskCreate,
  AcTaskListOut,
  AcTaskOut,
  AcTaskUpdate,
  AgentCreate,
  AgentHealthOut,
  AgentListOut,
  AlertListOut,
  AlertOut,
  ApprovalListOut,
  ApprovalOut,
  AuditListOut,
  CredentialCreate,
  CredentialCreated,
  DashboardOut,
  RunDetailOut,
  RunListOut,
  RunTimelineOut,
  UsageListOut,
  AgentRegistryOut as AcAgent,
} from "@/lib/contracts";

export type { AcAgent };

function useTenantKey(): string {
  return useAgentControl().installationId ?? "local";
}

// Intervalle de repli : le temps réel V1 (WS `ac:events`) pilote désormais la
// fraîcheur par invalidation ciblée (P9, gap 1). Le polling ne subsiste que comme
// filet de sécurité si le WS est indisponible — d'où un intervalle allongé (vs
// 15-20 s auparavant) pour ne pas doubler inutilement la charge quand le WS est up.
const FALLBACK_REFETCH_MS = 60_000;

// --- Dashboard / health -------------------------------------------------------

export function useDashboard(): UseQueryResult<DashboardOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "dashboard"],
    queryFn: ({ signal }) => acRequest<DashboardOut>("/dashboard", { signal }),
    refetchInterval: FALLBACK_REFETCH_MS,
  });
}

// --- Agents -------------------------------------------------------------------

export function useAgents(filters: Record<string, string | undefined> = {}): UseQueryResult<AgentListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "agents", filters],
    queryFn: ({ signal }) => acRequest<AgentListOut>("/agents", { query: filters, signal }),
  });
}

export function useAgent(id: string | null): UseQueryResult<AcAgent> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "agent", id],
    queryFn: ({ signal }) => acRequest<AcAgent>(`/agents/${id}`, { signal }),
    enabled: !!id,
  });
}

export function useAgentHealth(id: string | null): UseQueryResult<AgentHealthOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "agent", id, "health"],
    queryFn: ({ signal }) => acRequest<AgentHealthOut>(`/agents/${id}/health`, { signal }),
    enabled: !!id,
    refetchInterval: FALLBACK_REFETCH_MS,
  });
}

export function useRegisterAgent() {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AgentCreate) =>
      acRequest<AcAgent>("/agents", { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "agents"] });
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "dashboard"] });
    },
  });
}

export function useCreateCredential(agentId: string) {
  return useMutation({
    mutationFn: (body: CredentialCreate) =>
      acRequest<CredentialCreated>(`/agents/${agentId}/credentials`, {
        method: "POST",
        body,
      }),
  });
}

export function useAgentLifecycle(agentId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (action: "suspend" | "resume" | "archive") =>
      acRequest<AcAgent>(`/agents/${agentId}/${action}`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "agent", agentId] });
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "agents"] });
    },
  });
}

// --- Runs ---------------------------------------------------------------------

export function useRuns(filters: Record<string, string | undefined> = {}): UseQueryResult<RunListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "runs", filters],
    queryFn: ({ signal }) => acRequest<RunListOut>("/runs", { query: filters, signal }),
  });
}

export function useRun(id: string | null): UseQueryResult<RunDetailOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "run", id],
    queryFn: ({ signal }) => acRequest<RunDetailOut>(`/runs/${id}`, { signal }),
    enabled: !!id,
  });
}

export function useRunTimeline(id: string | null, cursor?: string): UseQueryResult<RunTimelineOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "run", id, "timeline", cursor ?? "0"],
    queryFn: ({ signal }) =>
      acRequest<RunTimelineOut>(`/runs/${id}/timeline`, { query: { cursor }, signal }),
    enabled: !!id,
  });
}

// --- Projets & tâches (P8) ----------------------------------------------------

export function useProjects(
  filters: Record<string, string | undefined> = {},
): UseQueryResult<AcProjectListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "projects", filters],
    queryFn: ({ signal }) => acRequest<AcProjectListOut>("/projects", { query: filters, signal }),
  });
}

export function useProject(id: string | null): UseQueryResult<AcProjectOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "project", id],
    queryFn: ({ signal }) => acRequest<AcProjectOut>(`/projects/${id}`, { signal }),
    enabled: !!id,
  });
}

export function useProjectTasks(
  projectId: string | null,
  filters: Record<string, string | undefined> = {},
): UseQueryResult<AcTaskListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "project", projectId, "tasks", filters],
    queryFn: ({ signal }) =>
      acRequest<AcTaskListOut>(`/projects/${projectId}/tasks`, { query: filters, signal }),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AcProjectCreate) =>
      acRequest<AcProjectOut>("/projects", { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "projects"] });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AcProjectUpdate) =>
      acRequest<AcProjectOut>(`/projects/${projectId}`, { method: "PATCH", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "project", projectId] });
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "projects"] });
    },
  });
}

export function useCreateTask(projectId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AcTaskCreate) =>
      acRequest<AcTaskOut>(`/projects/${projectId}/tasks`, { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "project", projectId, "tasks"] });
    },
  });
}

export function useUpdateTask(projectId: string, taskId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AcTaskUpdate) =>
      acRequest<AcTaskOut>(`/tasks/${taskId}`, { method: "PATCH", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "project", projectId, "tasks"] });
    },
  });
}

export function useAssignTask(projectId: string, taskId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (body: AcTaskAssign) =>
      acRequest<AcTaskOut>(`/tasks/${taskId}/assign`, { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "project", projectId, "tasks"] });
    },
  });
}

// --- Approbations -------------------------------------------------------------

export function useApprovals(status = "pending"): UseQueryResult<ApprovalListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "approvals", status],
    queryFn: ({ signal }) =>
      acRequest<ApprovalListOut>("/approvals", { query: { status }, signal }),
    refetchInterval: FALLBACK_REFETCH_MS,
  });
}

// `version` est OBLIGATOIRE côté serveur (`ApprovalDecisionIn`, control/schemas.py) : c'est le
// verrou optimiste qui garantit « jamais deux décisions » sur la même demande. Il était absent du
// corps envoyé ici, donc TOUTE décision depuis l'UI repartait en 422 — invisible car
// `RequestOptions.body` est typé `unknown` (client.ts) et qu'aucun test front n'exerce ce chemin.
// Le typer dans `input` rend désormais l'oubli impossible à la compilation, pas seulement corrigé
// à cet appel-ci.
export function useApprovalDecision(approvalId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (input: { decision: "approve" | "reject"; version: number; comment?: string }) =>
      acRequest<ApprovalOut>(`/approvals/${approvalId}/${input.decision}`, {
        method: "POST",
        body: { version: input.version, comment: input.comment ?? null },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "approvals"] });
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "dashboard"] });
    },
  });
}

// --- Alertes ------------------------------------------------------------------

export function useAlerts(status?: string): UseQueryResult<AlertListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "alerts", status ?? "all"],
    queryFn: ({ signal }) => acRequest<AlertListOut>("/alerts", { query: { status }, signal }),
    refetchInterval: FALLBACK_REFETCH_MS,
  });
}

export function useAlertAction(alertId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (action: "acknowledge" | "resolve") =>
      acRequest<AlertOut>(`/alerts/${alertId}/${action}`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "alerts"] });
      void qc.invalidateQueries({ queryKey: ["ac", tenant, "dashboard"] });
    },
  });
}

// --- Coûts / audit ------------------------------------------------------------

export function useUsage(filters: Record<string, string | undefined> = {}): UseQueryResult<UsageListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "usage", filters],
    queryFn: ({ signal }) => acRequest<UsageListOut>("/usage", { query: filters, signal }),
  });
}

export function useAudit(filters: Record<string, string | undefined> = {}): UseQueryResult<AuditListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "audit", filters],
    queryFn: ({ signal }) => acRequest<AuditListOut>("/audit", { query: filters, signal }),
  });
}
