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
  apps__api__agent_control__registry__schemas__AgentOut as AcAgent,
} from "@/lib/contracts";

export type { AcAgent };

function useTenantKey(): string {
  return useAgentControl().installationId ?? "local";
}

// --- Dashboard / health -------------------------------------------------------

export function useDashboard(): UseQueryResult<DashboardOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "dashboard"],
    queryFn: ({ signal }) => acRequest<DashboardOut>("/dashboard", { signal }),
    refetchInterval: 15_000,
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
    refetchInterval: 20_000,
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

// --- Approbations -------------------------------------------------------------

export function useApprovals(status = "pending"): UseQueryResult<ApprovalListOut> {
  const tenant = useTenantKey();
  return useQuery({
    queryKey: ["ac", tenant, "approvals", status],
    queryFn: ({ signal }) =>
      acRequest<ApprovalListOut>("/approvals", { query: { status }, signal }),
    refetchInterval: 20_000,
  });
}

export function useApprovalDecision(approvalId: string) {
  const qc = useQueryClient();
  const tenant = useTenantKey();
  return useMutation({
    mutationFn: (input: { decision: "approve" | "reject"; comment?: string }) =>
      acRequest<ApprovalOut>(`/approvals/${approvalId}/${input.decision}`, {
        method: "POST",
        body: { comment: input.comment ?? null },
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
    refetchInterval: 20_000,
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
