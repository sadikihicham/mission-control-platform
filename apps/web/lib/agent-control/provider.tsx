"use client";

// AgentControlProvider — point de montage unique du module embarqué (SP5 §1-2).
//
// Reçoit de l'hôte : mode `embedded`, `locale`, `installationId`, `capabilities`
// et un callback de navigation. En mode standalone (dev), l'adaptateur local
// résout ces valeurs depuis `/agent-control/v1/context` (réutilise le JWT hôte
// existant). Fournit : QueryClient unique, permissions (`can`), i18n (`t`), RTL.
//
// Invariant : aucune permission n'est décidée ici pour autoriser une action —
// l'API vérifie toujours. `can()` ne sert qu'à masquer/afficher l'UI (SP5 §14).
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import {
  createContext,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

import { acRequest } from "./client";
import { AC_RTL_LANGS, acTranslate, type AcLang } from "./i18n";
import type { Capability, HostContext } from "@/lib/contracts";

export interface AgentControlContextValue {
  embedded: boolean;
  locale: AcLang;
  rtl: boolean;
  installationId: string | null;
  capabilities: ReadonlySet<Capability>;
  can: (cap: Capability) => boolean;
  t: (key: string) => string;
  navigate: (path: string) => void;
  basePath: string;
  ready: boolean;
  error: unknown;
}

const Ctx = createContext<AgentControlContextValue | null>(null);

export function useAgentControl(): AgentControlContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAgentControl doit être utilisé sous <AgentControlProvider>");
  return v;
}

export interface AgentControlProviderProps {
  children: ReactNode;
  /** true quand monté dans un shell hôte (masque la nav locale, SP5 §15). */
  embedded?: boolean;
  /** Base de route du module (l'hôte peut le monter ailleurs). */
  basePath?: string;
  /** Fournis par l'hôte en mode embedded ; sinon résolus via /context. */
  locale?: AcLang;
  installationId?: string | null;
  capabilities?: Capability[];
  /** Callback de navigation hôte (SP5 §1). Défaut : window.location. */
  onNavigate?: (path: string) => void;
}

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Une seule source par ressource : pas de polling concurrent (SP5 invariant).
        refetchOnWindowFocus: false,
        retry: (count, err) => {
          const e = err as { status?: number; code?: string };
          if (e?.status === 401 || e?.status === 403 || e?.status === 404) return false;
          return count < 2;
        },
        staleTime: 10_000,
      },
    },
  });
}

interface InnerProps {
  children: ReactNode;
  embedded: boolean;
  basePath: string;
  locale: AcLang | undefined;
  installationId: string | null;
  capabilities: Capability[];
  onNavigate: (path: string) => void;
}

function Inner({
  children,
  embedded,
  basePath,
  locale,
  installationId,
  capabilities,
  onNavigate,
}: InnerProps) {
  // En standalone (props non fournies), on résout le contexte serveur.
  const needContext = capabilities.length === 0 || !installationId;
  const ctxQuery = useQuery<HostContext>({
    queryKey: ["ac", "context"],
    queryFn: ({ signal }) => acRequest<HostContext>("/context", { signal }),
    enabled: needContext,
  });

  const value = useMemo<AgentControlContextValue>(() => {
    const resolvedCaps: Capability[] =
      capabilities.length > 0
        ? capabilities
        : ((ctxQuery.data?.capabilities as Capability[] | undefined) ?? []);
    const caps = new Set<Capability>(resolvedCaps);
    const resolvedLocale: AcLang =
      locale ?? ((ctxQuery.data?.locale as AcLang | undefined) ?? "fr");
    const resolvedInstallation =
      installationId ?? ctxQuery.data?.installation?.id ?? null;
    return {
      embedded,
      locale: resolvedLocale,
      rtl: AC_RTL_LANGS.has(resolvedLocale),
      installationId: resolvedInstallation,
      capabilities: caps,
      can: (cap: Capability) => caps.has(cap),
      t: (key: string) => acTranslate(resolvedLocale, key),
      navigate: onNavigate,
      basePath,
      ready: !needContext || ctxQuery.isSuccess,
      error: ctxQuery.error,
    };
  }, [
    embedded,
    basePath,
    locale,
    installationId,
    capabilities,
    onNavigate,
    needContext,
    ctxQuery.data,
    ctxQuery.isSuccess,
    ctxQuery.error,
  ]);

  return (
    <Ctx.Provider value={value}>
      <div dir={value.rtl ? "rtl" : "ltr"} data-ac-embedded={embedded ? "1" : "0"}>
        {children}
      </div>
    </Ctx.Provider>
  );
}

export function AgentControlProvider(props: AgentControlProviderProps) {
  const qcRef = useRef<QueryClient | null>(null);
  qcRef.current ??= makeQueryClient();

  const defaultNavigate = (path: string) => {
    if (typeof window !== "undefined") window.location.assign(path);
  };

  return (
    <QueryClientProvider client={qcRef.current}>
      <Inner
        embedded={props.embedded ?? false}
        basePath={props.basePath ?? "/agent-control"}
        locale={props.locale}
        installationId={props.installationId ?? null}
        capabilities={props.capabilities ?? []}
        onNavigate={props.onNavigate ?? defaultNavigate}
      >
        {props.children}
      </Inner>
    </QueryClientProvider>
  );
}
