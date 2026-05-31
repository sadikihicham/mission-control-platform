// Client API — base URL configurable.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AgentState =
  | "idle" | "working" | "blocked" | "done" | "error" | "stale";

export type Agent = {
  agent: string;
  state: AgentState;
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
};

export type SubTask = {
  title: string;
  progress: number;
  state: string;
  agent: string | null;
};

export type Task = {
  id: string;
  title: string;
  module: string | null;
  progress: number;
  state: AgentState;
  agents: Agent[];
  subtasks: SubTask[];
};

export type ProjectSummary = {
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
};

export type ProjectDetail = ProjectSummary & {
  tasks: Task[];
  agents: Agent[];
};

/* ---------- Auth (JWT en localStorage) ---------- */

const TOKEN_KEY = "mc_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string): void {
  window.localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(res.status === 401 ? "Identifiants invalides" : `Erreur ${res.status}`);
  const data = (await res.json()) as { access_token: string };
  setToken(data.access_token);
  return data.access_token;
}

export function wsUrl(token: string): string {
  return `${API_URL.replace(/^http/, "ws")}/ws?token=${encodeURIComponent(token)}`;
}

/* ---------- Lecture ---------- */

async function get<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.status === 401) {
    // Token absent/expiré/invalidé (ex. rotation du secret) → retour au login.
    clearToken();
    if (typeof window !== "undefined") window.location.reload();
    throw new Error("session expirée");
  }
  if (!res.ok) throw new Error(`API ${path} ${res.status}`);
  return res.json();
}

export const getProjects = () => get<ProjectSummary[]>("/projects");
export const getProject = (id: string) =>
  get<ProjectDetail>(`/projects/${id}`);

export type GitInfo = {
  available: boolean;
  repo: string | null;
  url?: string;
  default_branch?: string;
  stars?: number;
  open_issues?: number;
  branch_count?: number;
  branches?: string[];
  commits?: { sha: string; message: string; author: string; date: string | null }[];
  prs?: { number: number; title: string; user: string }[];
  error?: string;
};
export const getProjectGit = (id: string) => get<GitInfo>(`/projects/${id}/git`);
export const getAgents = () => get<Agent[]>("/agents");

export type Activity = {
  type: string;
  state: string | null;
  task: string | null;
  progress: number | null;
  created_at: string | null;
};
export const getAgentActivity = (key: string) =>
  get<Activity[]>(`/agents/${encodeURIComponent(key)}/activity`);

/* ---------- Écriture (CRUD projets, rôle pm+) ---------- */

export type Me = { id: string; email: string; role: string };
export const getMe = () => get<Me>("/auth/me");

export const WRITE_ROLES = ["pm", "cto", "admin"];
export const canWrite = (role: string | null) => !!role && WRITE_ROLES.includes(role);

export const PROJECT_STATUSES = ["proposed", "validated", "in_dev", "done", "archived"] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

async function send<T>(method: string, path: string, body?: unknown): Promise<T | null> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") window.location.reload();
    throw new Error("session expirée");
  }
  if (res.status === 403) throw new Error("rôle insuffisant");
  if (!res.ok) throw new Error(`API ${path} ${res.status}`);
  return res.status === 204 ? null : (res.json() as Promise<T>);
}

export const createProject = (body: { name: string; description?: string; status?: string }) =>
  send<ProjectDetail>("POST", "/projects", body);
export const updateProject = (id: string, body: { status?: string; name?: string; description?: string; progress?: number }) =>
  send<ProjectDetail>("PATCH", `/projects/${id}`, body);
export const deleteProject = (id: string) => send<null>("DELETE", `/projects/${id}`);
