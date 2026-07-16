import { type APIRequestContext, type Page, expect } from "@playwright/test";

// URL de l'API isolée (login) — distincte de la stack docker partagée.
export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8009";

// Comptes déterministes créés par `apps/api/e2e_seed.py`.
export const USERS = {
  adminA: { email: "a@e2e.local", password: "pw-alpha-123" }, // tenant local (Alpha)
  adminB: { email: "b@e2e.local", password: "pw-beta-123" }, // tenant e2e-tenant-b (Beta)
  viewer: { email: "v@e2e.local", password: "pw-viewer-123" }, // tenant local, lecture seule
};

/** Obtient un JWT hôte via l'API (`/auth/login`). */
export async function login(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const res = await request.post(`${API_URL}/auth/login`, { data: { email, password } });
  expect(res.ok(), `login ${email} → ${res.status()}`).toBeTruthy();
  const body = (await res.json()) as { access_token: string };
  return body.access_token;
}

/** Injecte le JWT en localStorage (clé `mc_token`) puis navigue vers `path`. */
export async function gotoAs(page: Page, token: string, path: string): Promise<void> {
  await page.addInitScript((t) => window.localStorage.setItem("mc_token", t), token);
  await page.goto(path);
}
