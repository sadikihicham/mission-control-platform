// Client API — base URL configurable.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Types DTO GÉNÉRÉS depuis l'OpenAPI de l'API (source de vérité, plus aucune
// duplication manuelle) — cf. packages/contracts/ + lib/contracts.ts.
// Régénération : `make contracts`.
import type {
  ActivityOut,
  AgentOut,
  DashboardStats as DashboardStatsDTO,
  MeOut,
  ProjectDetail as ProjectDetailDTO,
  ProjectSummary as ProjectSummaryDTO,
  SubTask as SubTaskDTO,
  Task as TaskDTO,
} from "./contracts";

// Union d'états d'agent : affinage local (l'OpenAPI expose `state` en `string`).
export type AgentState =
  | "idle" | "working" | "blocked" | "done" | "error" | "stale";

// Ré-exports : les vues consomment ces alias, désormais adossés aux types générés.
export type Agent = AgentOut;
export type SubTask = SubTaskDTO;
export type Task = TaskDTO;
export type ProjectSummary = ProjectSummaryDTO;
export type ProjectDetail = ProjectDetailDTO;
export type DashboardStats = DashboardStatsDTO;

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

/** Changement de mot de passe pour l'utilisateur déjà connecté (authentifié, Bearer JWT). */
export async function changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
  const token = getToken();
  const res = await fetch(`${API_URL}/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) {
    // Token absent/expiré/invalidé → retour au login (même traitement que get()/send()).
    clearToken();
    if (typeof window !== "undefined") window.location.reload();
    throw new Error("session expirée");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const msg = typeof detail?.detail === "string" ? detail.detail : null;
    throw new Error(
      msg ??
        (res.status === 422
          ? "Le nouveau mot de passe doit contenir au moins 6 caractères."
          : res.status === 400
          ? "Mot de passe actuel incorrect."
          : `Erreur ${res.status}`)
    );
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

export type Activity = ActivityOut;
export const getAgentActivity = (key: string) =>
  get<Activity[]>(`/agents/${encodeURIComponent(key)}/activity`);

// KPIs dashboard (Contract C) — typés depuis l'OpenAPI généré.
export const getStats = () => get<DashboardStats>("/stats/dashboard");

/* ---------- Écriture (CRUD projets, rôle pm+) ---------- */

export type Me = MeOut;
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
