"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  canWrite,
  clearToken,
  createProject,
  deleteProject,
  getAgents,
  getMe,
  getProject,
  getProjects,
  getToken,
  updateProject,
  wsUrl,
  type Agent,
  type ProjectDetail,
  type ProjectSummary,
} from "@/lib/api";
import { Login } from "@/components/Login";
import { Toasts, type Toast } from "@/components/Toasts";
import { Shell } from "@/components/mc/Shell";
import { Icon } from "@/components/mc/icons";
import { ProjectCard, ProjectDetailPanel, ProjectsSummary } from "@/components/mc/Projects";
import { Overview } from "@/components/mc/Overview";
import { Hierarchy } from "@/components/mc/Hierarchy";
import { AgentDetail } from "@/components/mc/AgentDetail";
import { CommandPalette } from "@/components/mc/Command";
import { TweaksPanel, applyTweaks, TWEAK_DEFAULTS, type Tweaks } from "@/components/mc/Tweaks";
import { useI18n } from "@/lib/i18n";

function NewProjectForm({ onCreated, onClose }: { onCreated: () => void; onClose: () => void }) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("proposed");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <form
      className="np-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true); setErr(null);
        try { await createProject({ name, description, status }); onCreated(); onClose(); }
        catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
      }}
    >
      <div className="np-row">
        <input value={name} onChange={(e) => setName(e.target.value)} required placeholder={t("np_name")} autoFocus />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["proposed", "validated", "in_dev", "done", "archived"].map((s) => (<option key={s} value={s}>{s}</option>))}
        </select>
      </div>
      <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("np_desc")} />
      {err && <div style={{ color: "var(--block)", fontSize: 13 }}>{err}</div>}
      <div className="np-row">
        <button type="submit" className="btn primary" disabled={busy}>{Icon.plus({})} {busy ? t("np_creating") : t("np_create")}</button>
        <button type="button" className="btn ghost" onClick={onClose}>{t("np_cancel")}</button>
      </div>
    </form>
  );
}

export default function Home() {
  const [token, setTokenState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const [tweaks, setTweaks] = useState<Tweaks>(TWEAK_DEFAULTS);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [view, setView] = useState<"projects" | "overview" | "hierarchy">("projects");
  const [selected, setSelected] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [signal, setSignal] = useState(0);
  const [live, setLive] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const toastId = useRef(0);
  const { t } = useI18n();

  // Hydratation : token + tweaks (ambiance visuelle).
  useEffect(() => {
    setTokenState(getToken());
    try {
      const saved = localStorage.getItem("mc-tweaks");
      if (saved) setTweaks({ ...TWEAK_DEFAULTS, ...JSON.parse(saved) });
    } catch { /* défauts */ }
    setHydrated(true);
  }, []);

  // Applique les tweaks (variables CSS + thème) et persiste.
  useEffect(() => {
    applyTweaks(tweaks);
    localStorage.setItem("mc-tweaks", JSON.stringify(tweaks));
  }, [tweaks]);

  const setTw = useCallback((patch: Partial<Tweaks>) => setTweaks((prev) => ({ ...prev, ...patch })), []);

  // Rôle utilisateur.
  useEffect(() => {
    if (!token) { setRole(null); return; }
    getMe().then((m) => setRole(m.role)).catch(() => setRole(null));
  }, [token]);

  // Raccourci ⌘K / Ctrl+K pour la palette de commandes.
  useEffect(() => {
    if (!token) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdOpen((o) => !o); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [token]);

  // Charge la flotte quand la palette s'ouvre (pour la recherche d'agents).
  useEffect(() => {
    if (cmdOpen && agents.length === 0) getAgents().then(setAgents).catch(() => {});
  }, [cmdOpen, agents.length]);

  // WebSocket : tout message → refresh + toasts d'alerte.
  useEffect(() => {
    if (!token) return;
    let ws: WebSocket | null = null;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(wsUrl(token));
      ws.onopen = () => setLive(true);
      ws.onmessage = (ev) => {
        setSignal((s) => s + 1);
        try {
          const m = JSON.parse(ev.data as string);
          let toast: Toast | null = null;
          if (m.type === "agent.stale") toast = { id: ++toastId.current, kind: "stale", text: `${m.data?.agent_key} inactif` };
          else if (m.type === "agent.update" && m.data?.state === "blocked") toast = { id: ++toastId.current, kind: "blocked", text: `${m.data.agent_key} bloqué${m.data.blocker ? `: ${m.data.blocker}` : ""}` };
          else if (m.type === "agent.update" && m.data?.state === "error") toast = { id: ++toastId.current, kind: "error", text: `${m.data.agent_key} en erreur` };
          if (toast) { const tid = toast.id; setToasts((t) => [...t, toast as Toast]); setTimeout(() => setToasts((t) => t.filter((x) => x.id !== tid)), 6000); }
        } catch { /* ignore */ }
      };
      ws.onclose = () => { setLive(false); if (!closed) setTimeout(connect, 3000); };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => { closed = true; setLive(false); ws?.close(); };
  }, [token]);

  // Liste des projets (poll + signal).
  const reloadProjects = useCallback(async () => {
    try { setProjects(await getProjects()); } catch { /* 401 géré dans get() */ }
  }, []);
  useEffect(() => {
    if (!token || selected) return;
    let alive = true;
    const tick = () => { if (alive) reloadProjects(); };
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, [token, selected, signal, reloadProjects]);

  // Détail du projet sélectionné (poll + signal).
  useEffect(() => {
    if (!token || !selected) { setDetail(null); return; }
    let alive = true;
    const tick = async () => { try { const d = await getProject(selected); if (alive) setDetail(d); } catch { /* */ } };
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, [token, selected, signal]);

  // Flotte (vue d'ensemble) : tous les agents (poll + signal).
  useEffect(() => {
    if (!token || view !== "overview") return;
    let alive = true;
    const tick = async () => { try { const a = await getAgents(); if (alive) setAgents(a); } catch { /* */ } };
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, [token, view, signal]);

  // Garde les vitals de l'agent ouvert à jour pendant le poll.
  useEffect(() => {
    if (!selectedAgent) return;
    const fresh = agents.find((a) => a.agent === selectedAgent.agent);
    if (fresh && fresh.updated_at !== selectedAgent.updated_at) setSelectedAgent(fresh);
  }, [agents, selectedAgent]);

  if (!hydrated) return null;
  if (!token) return <Login onLogin={setTokenState} theme={tweaks.dark ? "dark" : "light"} onToggleTheme={() => setTw({ dark: !tweaks.dark })} />;

  const logout = () => { clearToken(); setTokenState(null); setSelected(null); };
  const writer = canWrite(role);
  const counts = {
    running: projects.reduce((s, p) => s + p.agents_active, 0),
    blocked: projects.reduce((s, p) => s + p.agents_blocked, 0),
    waiting: projects.reduce((s, p) => s + Math.max(0, p.agents_total - p.agents_active - p.agents_blocked), 0),
  };

  return (
    <>
      <Shell
        title={
          view === "hierarchy"
            ? t("nav_hierarchy")
            : view === "overview"
            ? selectedAgent ? (selectedAgent.label ?? selectedAgent.agent) : t("nav_overview")
            : selected && detail ? detail.name : t("nav_projects")
        }
        view={view}
        onNav={(v) => { setView(v as "projects" | "overview" | "hierarchy"); setSelected(null); setSelectedAgent(null); setShowNew(false); }}
        role={role}
        live={live}
        theme={tweaks.dark ? "dark" : "light"}
        onToggleTheme={() => setTw({ dark: !tweaks.dark })}
        counts={counts}
        canNew={writer}
        onNew={() => { setView("projects"); setSelected(null); setShowNew(true); }}
        onLogout={logout}
        onCommand={() => setCmdOpen(true)}
        onTweaks={() => setTweaksOpen(true)}
      >
        {view === "hierarchy" ? (
          <Hierarchy
            projects={projects}
            onOpenProject={(id) => { setView("projects"); setSelected(id); }}
            onOpenAgent={(a) => { setView("overview"); setSelectedAgent(a); }}
          />
        ) : view === "overview" ? (
          selectedAgent ? (
            <AgentDetail agent={selectedAgent} subtasks={[]} onBack={() => setSelectedAgent(null)} />
          ) : (
            <Overview agents={agents} onOpenAgent={setSelectedAgent} />
          )
        ) : selected && detail ? (
          <ProjectDetailPanel
            project={detail}
            onBack={() => setSelected(null)}
            canEdit={writer && detail.editable}
            onStatus={writer && detail.editable ? async (status) => { await updateProject(detail.id, { status }); setSignal((s) => s + 1); } : undefined}
            onRepo={writer && detail.editable ? async (repo) => { await updateProject(detail.id, { repo }); setSignal((s) => s + 1); } : undefined}
            onDelete={writer && detail.editable ? async () => { await deleteProject(detail.id); setSelected(null); reloadProjects(); } : undefined}
          />
        ) : (
          <div className="pj-page">
            <ProjectsSummary projects={projects} />
            {showNew && writer && <NewProjectForm onCreated={reloadProjects} onClose={() => setShowNew(false)} />}
            <div className="pcard-grid">
              {projects.map((p) => (
                <ProjectCard
                  key={p.id}
                  p={p}
                  onOpen={() => setSelected(p.id)}
                  onDelete={writer && p.editable ? async () => { await deleteProject(p.id); reloadProjects(); } : undefined}
                />
              ))}
            </div>
          </div>
        )}
      </Shell>
      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        projects={projects}
        agents={agents}
        actions={{
          goProjects: () => { setView("projects"); setSelected(null); },
          goOverview: () => { setView("overview"); setSelected(null); },
          openProject: (id) => { setView("projects"); setSelected(id); },
          newProject: writer ? () => { setView("projects"); setSelected(null); setShowNew(true); } : undefined,
          toggleTheme: () => setTw({ dark: !tweaks.dark }),
          logout,
        }}
      />
      <TweaksPanel open={tweaksOpen} onClose={() => setTweaksOpen(false)} t={tweaks} set={setTw} />
      <Toasts toasts={toasts} />
    </>
  );
}
