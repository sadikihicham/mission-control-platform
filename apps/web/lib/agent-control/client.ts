// Client HTTP unique du module Agent Control embarqué.
//
// Responsabilités (SP5 §3) : une seule porte réseau, erreurs typées (enveloppe
// V1 `{error:{code,message,...}}`), pagination par curseur, abort, contexte
// installation. L'auth réutilise le JWT hôte existant (adaptateur local de dev).
// Aucune permission n'est décidée ici : l'API vérifie toujours côté serveur ;
// le client se contente de remonter 401/403/404 typés pour l'UI.
import { API_URL, getToken } from "@/lib/api";

export type ErrorCode =
  | "unauthenticated"
  | "credential_invalid"
  | "credential_revoked"
  | "permission_denied"
  | "tenant_required"
  | "tenant_forbidden"
  | "not_found"
  | "validation_error"
  | "conflict"
  | "idempotency_conflict"
  | "sequence_out_of_order"
  | "state_conflict"
  | "approval_required"
  | "budget_exceeded"
  | "rate_limited"
  | "not_implemented"
  | "internal_error"
  | "network_error";

export class AcApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly requestId: string | null;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: ErrorCode,
    message: string,
    requestId: string | null = null,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "AcApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }

  get isAuth(): boolean {
    return this.status === 401;
  }
  get isForbidden(): boolean {
    return this.status === 403;
  }
  get isNotFound(): boolean {
    return this.status === 404;
  }
  get isOffline(): boolean {
    return this.code === "network_error";
  }
}

export const AC_BASE = "/agent-control/v1";

export interface PageInfo {
  next_cursor: string | null;
  limit: number;
  has_more: boolean;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  signal?: AbortSignal;
  /** Identifiant d'installation courant (contexte tenant), propagé en en-tête. */
  installationId?: string | null;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}${AC_BASE}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function parseError(res: Response): Promise<AcApiError> {
  let code: ErrorCode = "internal_error";
  let message = res.statusText || "Erreur";
  let requestId: string | null = null;
  let details: Record<string, unknown> = {};
  try {
    const data = (await res.json()) as {
      error?: { code?: ErrorCode; message?: string; request_id?: string; details?: Record<string, unknown> };
      detail?: string;
    };
    if (data.error) {
      code = data.error.code ?? code;
      message = data.error.message ?? message;
      requestId = data.error.request_id ?? null;
      details = data.error.details ?? {};
    } else if (typeof data.detail === "string") {
      message = data.detail;
    }
  } catch {
    /* corps non-JSON : on garde le statut brut */
  }
  return new AcApiError(res.status, code, message, requestId, details);
}

/** Appel réseau unique : JWT hôte, en-tête installation, erreurs typées, abort. */
export async function acRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.installationId) headers["X-MC-Installation"] = opts.installationId;

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
      cache: "no-store",
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new AcApiError(0, "network_error", "Réseau indisponible (hors-ligne)");
  }
  if (res.status === 204) return undefined as T;
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}
