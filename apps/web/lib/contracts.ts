// -----------------------------------------------------------------------------
// FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.
// Source : OpenAPI de l'API (packages/contracts/openapi.json).
// Régénérer : `make contracts` (cf. packages/contracts/generate.py).
// Types alignés sur les schémas Pydantic (Contrats C/D/E gelés).
// -----------------------------------------------------------------------------


export interface ActivityOut {
  type: string;
  state: string | null;
  task: string | null;
  progress: number | null;
  created_at: string | null;
}


export interface AgentOut {
  agent: string;
  state: string;
  task: string | null;
  module: string | null;
  label: string | null;
  branch: string | null;
  blocker: string | null;
  progress: number;
  tasks_done: number | null;
  tasks_total: number | null;
  updated_at: string | null;
  age_seconds: number | null;
  token_issued_at: string | null;
}


export type Capability = "view" | "operate" | "manage_agents" | "manage_projects" | "approve" | "view_costs" | "admin";


export interface DashboardStats {
  agents_total: number;
  agents_active: number;
  agents_blocked: number;
  agents_stale: number;
  agents_done: number;
  agents_error: number;
  overall_progress: number;
}


export interface ForgotPasswordIn {
  email: string;
}


export interface ForgotPasswordOut {
  message: string;
  dev_token: string | null;
}


export interface HeartbeatIn {
  agent: string;
  state: string;
  project: string | null;
  task: string | null;
  progress: number | null;
  tasks_done: number | null;
  tasks_total: number | null;
  module: string | null;
  branch: string | null;
  blocker: string | null;
  meta: Record<string, unknown> | null;
}


export interface HostContext {
  request_id: string;
  installation: InstallationRef;
  tenant: TenantRef;
  user: UserRef;
  capabilities: Capability[];
  locale: string;
  timezone: string;
}


export interface InstallationRef {
  id: string;
  installation_key: string;
  external_tenant_id: string;
  status: string;
}


export interface LoginIn {
  email: string;
  password: string;
}


export interface MeOut {
  id: string;
  email: string;
  role: string;
  full_name: string | null;
  civility: string | null;
  is_active: boolean;
}


export interface MessageOut {
  message: string;
}


export interface ProjectCreate {
  name: string;
  slug: string | null;
  description: string | null;
  status: string;
  repo: string | null;
}


export interface ProjectDetail {
  id: string;
  name: string;
  description: string | null;
  status: string;
  progress: number;
  tasks_total: number;
  tasks_done: number;
  agents_total: number;
  agents_active: number;
  agents_blocked: number;
  editable: boolean;
  repo: string | null;
  tasks: Task[];
  agents: AgentOut[];
}


export interface ProjectSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  progress: number;
  tasks_total: number;
  tasks_done: number;
  agents_total: number;
  agents_active: number;
  agents_blocked: number;
  editable: boolean;
  repo: string | null;
}


export interface ProjectUpdate {
  name: string | null;
  description: string | null;
  status: string | null;
  progress: number | null;
  repo: string | null;
}


export interface ResetPasswordIn {
  token: string;
  new_password: string;
}


export type Role = "viewer" | "developer" | "pm" | "cto" | "admin";


export interface SubTask {
  title: string;
  progress: number;
  state: string;
  agent: string | null;
}


export interface Task {
  id: string;
  title: string;
  module: string | null;
  progress: number;
  state: string;
  agents: AgentOut[];
  subtasks: SubTask[];
}


export interface TenantRef {
  external_tenant_id: string;
  name: string;
  slug: string;
  status: string;
  feature_flags: Record<string, unknown>;
}


export interface TokenOut {
  access_token: string;
  token_type: string;
}


export interface UserCreateIn {
  email: string;
  password: string;
  role: Role;
  full_name: string | null;
  civility: string | null;
}


export interface UserRef {
  external_user_id: string;
  local_user_id: string | null;
  email: string | null;
  display_name: string | null;
  status: string;
}


export interface UserUpdateIn {
  role: Role | null;
  full_name: string | null;
  civility: string | null;
  is_active: boolean | null;
}
