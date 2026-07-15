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
  // Identité par agent (Contract D) : date d'enrôlement, ou null s'il tourne
  // encore avec le secret partagé MC_INGEST_TOKEN.
  token_issued_at: string | null;
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
  // Droit d'édition calculé côté API selon le rôle de l'appelant.
  editable?: boolean;
};

export type ProjectDetail = ProjectSummary & {
  tasks: Task[];
  agents: Agent[];
  // Dépôt GitHub associé (lié via PATCH /projects/{id}).
  repo?: string | null;
};

/* ---------- Auth (JWT en localStorage) ---------- */

const TOKEN_KEY = "mc_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string): void {
  window.localStorage.setItem(TOKEN_KEY, t);
  // Une session active annule un éventuel "déconnexion manuelle" précédent.
  window.sessionStorage.removeItem("mc_logged_out");
}
export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

/* ---------- Connexion automatique (dev/démo) ----------
   Ouvre la session sans passer par le formulaire. Pilotée par l'env :
   - NEXT_PUBLIC_AUTO_LOGIN=0  désactive (défaut: activé)
   - NEXT_PUBLIC_AUTO_LOGIN_EMAIL / _PASSWORD  surchargent les identifiants par défaut.
   La déconnexion manuelle pose un drapeau (sessionStorage) pour ne PAS se reconnecter
   tout de suite — on peut donc toujours revenir à l'écran de login. */
export const AUTO_LOGIN = process.env.NEXT_PUBLIC_AUTO_LOGIN !== "0";
const DEFAULT_EMAIL = process.env.NEXT_PUBLIC_AUTO_LOGIN_EMAIL ?? "demo@infinity.ae";
const DEFAULT_PASSWORD = process.env.NEXT_PUBLIC_AUTO_LOGIN_PASSWORD ?? "password";
const LOGOUT_FLAG = "mc_logged_out";

export function markLoggedOut(): void {
  if (typeof window !== "undefined") window.sessionStorage.setItem(LOGOUT_FLAG, "1");
}

/** Tente une connexion auto avec les identifiants par défaut. Renvoie le token
 *  ou null (désactivée, déconnexion manuelle en cours, ou échec silencieux). */
export async function autoLogin(): Promise<string | null> {
  if (!AUTO_LOGIN || typeof window === "undefined") return null;
  if (window.sessionStorage.getItem(LOGOUT_FLAG)) return null;
  try {
    return await login(DEFAULT_EMAIL, DEFAULT_PASSWORD);
  } catch {
    return null; // API down / identifiants invalides → on retombe sur le formulaire.
  }
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

export async function forgotPassword(email: string): Promise<{ message: string; dev_token: string | null }> {
  const res = await fetch(`${API_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(`Erreur ${res.status}`);
  return res.json();
}

export async function resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  const res = await fetch(`${API_URL}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? (res.status === 400 ? "Jeton invalide ou expiré" : `Erreur ${res.status}`));
  }
  return res.json();
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

export type Me = {
  id: string;
  email: string;
  role: string;
  full_name: string | null;
  civility: string | null;
  is_active: boolean;
};
export const getMe = () => get<Me>("/auth/me");

export const WRITE_ROLES = ["pm", "cto", "admin"];
export const canWrite = (role: string | null) => !!role && WRITE_ROLES.includes(role);

export const ROLES = ["viewer", "developer", "pm", "cto", "admin"] as const;

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
export const updateProject = (id: string, body: { status?: string; name?: string; description?: string; progress?: number; repo?: string | null }) =>
  send<ProjectDetail>("PATCH", `/projects/${id}`, body);
export const deleteProject = (id: string) => send<null>("DELETE", `/projects/${id}`);

/* ---------- Administration (rôle admin) ---------- */

export const getUsers = () => get<Me[]>("/auth/users");
export const createUser = (body: { email: string; password: string; role?: string; full_name?: string; civility?: string }) =>
  send<Me>("POST", "/auth/users", body);
export const updateUser = (id: string, body: { role?: string; full_name?: string; civility?: string; is_active?: boolean }) =>
  send<Me>("PATCH", `/auth/users/${id}`, body);
export const revokeAgentToken = (agentKey: string) =>
  send<null>("POST", `/agents/${encodeURIComponent(agentKey)}/revoke-token`);
