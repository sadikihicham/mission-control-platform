"use client";

// Temps réel V1 côté client (SP5 §5, gap 1 P9) — bascule du polling vers
// l'invalidation ciblée par événement. Le WS ne transporte que des SIGNAUX
// légers (`WsMessageV1`) ; la donnée fait toujours foi via HTTP : à chaque
// événement on invalide la query React Query concernée, qui refetch la source.
// Un WS indisponible n'empêche jamais l'affichage — les queries gardent un
// intervalle de rafraîchissement de repli (voir hooks.ts).
import { useCallback, useEffect, useRef, useState } from "react";

import { type QueryClient, useQueryClient } from "@tanstack/react-query";

import { API_URL, getToken } from "@/lib/api";

export interface WsMessage {
  id: string;
  type: string;
  tenant_id: string;
  topic: string;
  sequence: number;
  data: Record<string, unknown>;
  occurred_at: string;
}

function acWsUrl(token: string, installationId: string | null): string {
  const base = API_URL.replace(/^http/, "ws");
  const params = new URLSearchParams({ token });
  if (installationId) params.set("installation_id", installationId);
  return `${base}/agent-control/ws?${params.toString()}`;
}

/**
 * Traduit un événement V1 en invalidations de queries ciblées.
 *
 * Clés alignées sur `hooks.ts` (`["ac", tenant, ...]`). On invalide toujours la
 * famille concernée + le dashboard (agrégats). L'invalidation est idempotente et
 * peu coûteuse : React Query ne refetch que les queries actives (montées).
 */
function invalidateForEvent(qc: QueryClient, tenant: string, msg: WsMessage): void {
  const inv = (key: unknown[]) => void qc.invalidateQueries({ queryKey: key });
  const type = msg.type;
  const data = msg.data ?? {};
  const agentId = typeof data.agent_id === "string" ? data.agent_id : null;
  const runId = typeof data.run_id === "string" ? data.run_id : null;

  if (type.startsWith("agent.")) {
    inv(["ac", tenant, "agents"]);
    if (agentId) inv(["ac", tenant, "agent", agentId]);
  } else if (type.startsWith("run.")) {
    inv(["ac", tenant, "runs"]);
    if (runId) inv(["ac", tenant, "run", runId]);
  } else if (type.startsWith("command.")) {
    inv(["ac", tenant, "runs"]);
    if (runId) inv(["ac", tenant, "run", runId]);
  } else if (type.startsWith("approval.")) {
    inv(["ac", tenant, "approvals"]);
  } else if (type.startsWith("alert.")) {
    inv(["ac", tenant, "alerts"]);
  } else if (type === "usage.recorded" || type.startsWith("budget.")) {
    inv(["ac", tenant, "usage"]);
  }
  // Le dashboard agrège tout : toujours rafraîchi.
  inv(["ac", tenant, "dashboard"]);
}

export interface AcRealtime {
  connected: boolean;
  subscribe: (topics: string[]) => void;
  unsubscribe: (topics: string[]) => void;
}

// Topics scalaires souscrits en permanence (dashboard : alertes/budgets/approbations).
const BASE_TOPICS = ["fleet", "approvals"];

/**
 * Connexion WS gérée au niveau du provider : reconnexion à backoff, souscription
 * des topics de base + topics dynamiques (vues de détail via `subscribe`).
 */
export function useAcRealtime(installationId: string | null): AcRealtime {
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const topicsRef = useRef<Set<string>>(new Set(BASE_TOPICS));
  const tenantRef = useRef<string>(installationId ?? "local");
  const closedRef = useRef(false);
  const backoffRef = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  tenantRef.current = installationId ?? "local";

  const send = useCallback((action: "subscribe" | "unsubscribe", topics: string[]) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && topics.length > 0) {
      ws.send(JSON.stringify({ action, topics }));
    }
  }, []);

  const subscribe = useCallback(
    (topics: string[]) => {
      const fresh = topics.filter((t) => !topicsRef.current.has(t));
      fresh.forEach((t) => topicsRef.current.add(t));
      send("subscribe", fresh);
    },
    [send],
  );

  const unsubscribe = useCallback(
    (topics: string[]) => {
      const removable = topics.filter((t) => !BASE_TOPICS.includes(t));
      removable.forEach((t) => topicsRef.current.delete(t));
      send("unsubscribe", removable);
    },
    [send],
  );

  useEffect(() => {
    const token = getToken();
    if (!token || typeof window === "undefined") return;
    closedRef.current = false;

    const connect = () => {
      if (closedRef.current) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(acWsUrl(token, installationId));
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        // (re)souscrit tous les topics connus après (re)connexion.
        ws.send(JSON.stringify({ action: "subscribe", topics: [...topicsRef.current] }));
      };
      ws.onmessage = (ev) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(ev.data as string);
        } catch {
          return;
        }
        if (!msg || typeof msg.type !== "string") return; // "ready"/"pong" ignorés
        if (!("tenant_id" in msg) || !("topic" in msg)) return;
        invalidateForEvent(qc, tenantRef.current, msg);
      };
      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        scheduleReconnect();
      };
      ws.onerror = () => {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      };
    };

    const scheduleReconnect = () => {
      if (closedRef.current) return;
      const delay = Math.min(backoffRef.current, 30_000);
      backoffRef.current = Math.min(backoffRef.current * 2, 30_000);
      // Jitter pour éviter les reconnexions synchronisées.
      const jittered = delay + Math.floor(Math.random() * 500);
      reconnectTimer.current = setTimeout(connect, jittered);
    };

    connect();

    return () => {
      closedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onclose = null;
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      }
      setConnected(false);
    };
    // Reconnecte si le tenant change (nouvelle installation résolue).
  }, [installationId, qc]);

  return { connected, subscribe, unsubscribe };
}

/**
 * Souscrit un topic dynamique (`agent:{id}`, `run:{id}`, `project:{id}`) le temps
 * qu'une vue de détail est montée. Sans-op si `topic` est nul. Accepte le contexte
 * Agent Control (`subscribeTopics`/`unsubscribeTopics`).
 */
export function useAcTopic(
  ac: {
    subscribeTopics: (topics: string[]) => void;
    unsubscribeTopics: (topics: string[]) => void;
  },
  topic: string | null,
): void {
  const { subscribeTopics, unsubscribeTopics } = ac;
  useEffect(() => {
    if (!topic) return;
    subscribeTopics([topic]);
    return () => unsubscribeTopics([topic]);
  }, [topic, subscribeTopics, unsubscribeTopics]);
}
