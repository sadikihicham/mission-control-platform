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


export interface AgentCreate {
  local_key: string;
  display_name: string | null;
  description: string | null;
  runtime: string | null;
  provider: string | null;
  client_version: string | null;
  environment: string | null;
  capabilities: string[];
}


export interface AgentHealthOut {
  agent_key: string;
  status: string;
  state: string;
  last_heartbeat: string | null;
  seconds_since_heartbeat: number | null;
  healthy: boolean;
  active_runs: number;
  open_alerts: number;
}


export interface AgentListOut {
  items: apps__api__agent_control__registry__schemas__AgentOut[];
  page_info: PageInfo;
}


export interface AgentUpdate {
  display_name: string | null;
  description: string | null;
  runtime: string | null;
  provider: string | null;
  client_version: string | null;
  environment: string | null;
  capabilities: string[] | null;
}


export interface AgentsSummary {
  total: number;
  active: number;
  suspended: number;
  revoked: number;
  archived: number;
  working: number;
  idle: number;
  blocked: number;
  stale: number;
  done: number;
  error: number;
}


export interface AlertListOut {
  items: AlertOut[];
  page_info: PageInfo;
}


export interface AlertOut {
  id: string;
  alert_type: string;
  severity: string;
  status: string;
  target_type: string | null;
  target_id: string | null;
  dedup_key: string;
  title: string;
  details: Record<string, unknown>;
  opened_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  version: number;
}


export interface ApprovalDecisionIn {
  version: number;
  comment: string | null;
}


export interface ApprovalListOut {
  items: ApprovalOut[];
  page_info: PageInfo;
}


export interface ApprovalOut {
  id: string;
  project_id: string | null;
  task_id: string | null;
  run_id: string | null;
  agent_id: string;
  policy_id: string | null;
  action_type: string;
  risk_level: string;
  title: string;
  context: Record<string, unknown>;
  requested_by: string | null;
  requested_by_agent: boolean;
  status: string;
  assigned_to: string | null;
  expires_at: string | null;
  decided_at: string | null;
  decision_by: string | null;
  decision_comment: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}


export interface AuditEntryOut {
  id: string;
  actor_type: string;
  actor_id: string | null;
  actor_label: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  request_id: string | null;
  ip_hash: string | null;
  created_at: string;
}


export interface AuditListOut {
  items: AuditEntryOut[];
  page_info: PageInfo;
}


export interface BudgetCreate {
  scope_type: string;
  scope_id: string | null;
  period: string;
  currency: string;
  amount_limit: number | string;
  thresholds: number[] | null;
  on_exceed: string;
  description: string | null;
}


export interface BudgetListOut {
  items: BudgetStatusOut[];
  page_info: PageInfo;
}


export interface BudgetStatusOut {
  id: string;
  scope_type: string;
  scope_id: string | null;
  period: string;
  currency: string;
  amount_limit: string;
  thresholds: number[];
  on_exceed: string;
  status: string;
  description: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  consumed: string;
  pct: string;
}


export interface BudgetUpdate {
  version: number;
  amount_limit: number | string | null;
  thresholds: number[] | null;
  on_exceed: string | null;
  period: string | null;
  status: string | null;
  description: string | null;
}


export type Capability = "view" | "operate" | "manage_agents" | "manage_projects" | "approve" | "view_costs" | "admin";


export interface ChangePasswordIn {
  current_password: string;
  new_password: string;
}


export interface CommandListOut {
  items: CommandOut[];
  page_info: PageInfo;
}


export interface CommandOut {
  id: string;
  agent_id: string;
  run_id: string | null;
  command_type: string;
  payload: Record<string, unknown>;
  status: string;
  idempotency_key: string;
  approval_request_id: string | null;
  policy_effect: string | null;
  risk_level: string | null;
  released_at: string | null;
  expires_at: string | null;
  delivered_at: string | null;
  acknowledged_at: string | null;
  result_at: string | null;
  result_status: string | null;
  error_message: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}


export interface CommandResultIn {
  status: string;
  result_payload: Record<string, unknown>;
  error_message: string | null;
}


export interface CommandSubmit {
  command_type: string;
  payload: Record<string, unknown>;
  idempotency_key: string | null;
  expires_in_seconds: number | null;
  risk_level: string | null;
}


export interface CostSummary {
  total_cost: string;
  currency: string;
  record_count: number;
}


export interface CredentialCreate {
  scopes: string[];
  expires_at: string | null;
}


export interface CredentialCreated {
  id: string;
  agent_id: string;
  key_prefix: string;
  secret: string;
  scopes: string[];
  expires_at: string | null;
  created_by: string | null;
  created_at: string;
}


export interface DashboardOut {
  installation_id: string;
  agents: AgentsSummary;
  runs: RunsSummary;
  approvals_pending: number;
  alerts_open: number;
  cost: CostSummary;
  overall_progress: number;
}


export interface DashboardStats {
  agents_total: number;
  agents_active: number;
  agents_blocked: number;
  agents_stale: number;
  agents_done: number;
  agents_error: number;
  overall_progress: number;
}


export interface EventEnvelopeV1 {
  event_id: string;
  agent_key: string;
  sequence: number;
  event_type: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  run_id: string | null;
  project_id: string | null;
  task_id: string | null;
  trace_id: string | null;
  client_version: string | null;
}


export interface ForgotPasswordIn {
  email: string;
}


export interface ForgotPasswordOut {
  message: string;
  dev_token: string | null;
}


export interface HealthOut {
  status: string;
  installation_id: string;
  installation_status: string;
  tenant_status: string;
  capabilities: string[];
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


export interface IngestEventsRequest {
  events: EventEnvelopeV1[];
}


export interface IngestEventsResponse {
  accepted: number;
  duplicates: number;
  rejected: number;
  last_sequence: number;
}


export interface IngestHeartbeatResponse {
  agent_key: string;
  state: string;
  last_sequence: number;
  last_heartbeat: string | null;
  applied: boolean;
}


export interface IngestHeartbeatV1 {
  agent_key: string;
  state: string;
  run_id: string | null;
  task: string | null;
  progress: number | null;
  sequence: number | null;
  occurred_at: string | null;
  metrics: Record<string, unknown>;
}


export interface InstallationOut {
  id: string;
  installation_key: string;
  external_tenant_id: string;
  status: string;
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


export interface PageInfo {
  next_cursor: string | null;
  limit: number;
  has_more: boolean;
}


export interface PolicyCreate {
  scope_type: string;
  scope_id: string | null;
  action_type: string;
  effect: string;
  risk_level: string | null;
  conditions: Record<string, unknown>;
  priority: number;
  description: string | null;
}


export interface PolicyListOut {
  items: PolicyOut[];
  page_info: PageInfo;
}


export interface PolicyOut {
  id: string;
  scope_type: string;
  scope_id: string | null;
  action_type: string;
  effect: string;
  risk_level: string | null;
  conditions: Record<string, unknown>;
  priority: number;
  status: string;
  description: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}


export interface PolicyUpdate {
  version: number;
  scope_type: string | null;
  scope_id: string | null;
  action_type: string | null;
  effect: string | null;
  risk_level: string | null;
  conditions: Record<string, unknown> | null;
  priority: number | null;
  status: string | null;
  description: string | null;
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
  agents: apps__api__schemas__agent__AgentOut[];
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


export interface RunDetailOut {
  id: string;
  project_id: string | null;
  task_id: string | null;
  agent_id: string;
  external_run_key: string | null;
  objective: string | null;
  state: string;
  retry_of_run_id: string | null;
  attempt: number;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  result_summary: string | null;
  error_code: string | null;
  error_message: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  steps: RunStepOut[];
}


export interface RunListOut {
  items: RunOut[];
  page_info: PageInfo;
}


export interface RunOut {
  id: string;
  project_id: string | null;
  task_id: string | null;
  agent_id: string;
  external_run_key: string | null;
  objective: string | null;
  state: string;
  retry_of_run_id: string | null;
  attempt: number;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  result_summary: string | null;
  error_code: string | null;
  error_message: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}


export interface RunStepOut {
  id: string;
  sequence: number;
  step_type: string;
  name: string | null;
  state: string;
  tool_name: string | null;
  input_summary: string | null;
  output_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}


export interface RunTimelineOut {
  run_id: string;
  items: TimelineEntryOut[];
  page_info: PageInfo;
}


export interface RunsSummary {
  total: number;
  running: number;
  queued: number;
  starting: number;
  waiting_approval: number;
  blocked: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  timed_out: number;
}


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
  agents: apps__api__schemas__agent__AgentOut[];
  subtasks: SubTask[];
}


export interface TenantRef {
  external_tenant_id: string;
  name: string;
  slug: string;
  status: string;
  feature_flags: Record<string, unknown>;
}


export interface TimelineEntryOut {
  event_id: string;
  event_type: string;
  sequence: number;
  occurred_at: string;
  payload: Record<string, unknown>;
}


export interface TokenOut {
  access_token: string;
  token_type: string;
}


export interface UsageListOut {
  summary: UsageSummaryOut;
  items: UsageRecordOut[];
  page_info: PageInfo;
}


export interface UsageRecordOut {
  id: string;
  agent_id: string;
  project_id: string | null;
  run_id: string | null;
  provider: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  calls: number;
  duration_ms: number | null;
  currency: string;
  cost: string;
  pricing_version: string;
  occurred_at: string;
}


export interface UsageSummaryOut {
  total_cost: string;
  total_tokens: number;
  total_calls: number;
  currency: string;
  record_count: number;
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


export interface apps__api__agent_control__registry__schemas__AgentOut {
  id: string;
  agent_key: string;
  installation_id: string;
  display_name: string | null;
  description: string | null;
  runtime: string | null;
  provider: string | null;
  client_version: string | null;
  environment: string | null;
  capabilities: string[];
  status: string;
  state: string;
  last_heartbeat: string | null;
  last_sequence: number;
  registered_by: string | null;
  registered_at: string | null;
  revoked_at: string | null;
  project_ids: string[];
  created_at: string;
  updated_at: string;
}


export interface apps__api__schemas__agent__AgentOut {
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
