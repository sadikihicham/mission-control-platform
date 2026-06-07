"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { Agent, ProjectSummary } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { statusOf } from "@/lib/mc";
import { useI18n } from "@/lib/i18n";

const deburr = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");
function fuzzy(q: string, text: string): number {
  if (!q) return 0;
  q = deburr(q.toLowerCase());
  text = deburr(text.toLowerCase());
  let qi = 0, score = 0, prev = -1;
  for (let i = 0; i < text.length && qi < q.length; i++) {
    if (text[i] === q[qi]) { score += prev >= 0 ? i - prev : 0; prev = i; qi++; }
  }
  return qi === q.length ? score - (text.startsWith(q) ? 50 : 0) : Infinity;
}

type CmdItem = {
  id: string; label: string; group: "view" | "action" | "project" | "agent";
  icon?: (p?: any) => JSX.Element; kw: string; run: () => void;
  sub?: string; clr?: string;
};

export type CmdActions = {
  goProjects: () => void;
  goOverview: () => void;
  openProject: (id: string) => void;
  newProject?: () => void;
  toggleTheme: () => void;
  openTweaks?: () => void;
  logout: () => void;
};

export function CommandPalette({
  open,
  onClose,
  projects,
  agents,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  projects: ProjectSummary[];
  agents: Agent[];
  actions: CmdActions;
}) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => inputRef.current?.focus(), 30); } }, [open]);

  const items = useMemo<CmdItem[]>(() => {
    const views: CmdItem[] = [
      { id: "v-proj", icon: Icon.folder, label: t("nav_projects"), group: "view", kw: "projets projects", run: actions.goProjects },
      { id: "v-fleet", icon: Icon.grid, label: t("nav_overview"), group: "view", kw: "flotte fleet overview agents vue ensemble", run: actions.goOverview },
    ];
    const acts: CmdItem[] = [
      ...(actions.newProject ? [{ id: "a-new", icon: Icon.plus, label: t("a_new"), group: "action" as const, kw: "nouveau projet new create", run: actions.newProject }] : []),
      { id: "a-theme", icon: Icon.sun, label: t("a_theme"), group: "action", kw: "theme clair sombre dark light", run: actions.toggleTheme },
      ...(actions.openTweaks ? [{ id: "a-tweaks", icon: Icon.sliders, label: t("tw_title"), group: "action" as const, kw: "tweaks ambiance presets aurora reglages settings", run: actions.openTweaks }] : []),
      { id: "a-logout", icon: Icon.logout, label: t("a_logout"), group: "action", kw: "deconnexion logout sortir", run: actions.logout },
    ];
    const proj: CmdItem[] = projects.map((p) => ({
      id: "pj-" + p.id, label: p.name, group: "project", kw: p.name + " " + (p.description ?? "") + " " + p.status,
      sub: `${p.progress}% · ${p.status}`, run: () => actions.openProject(p.id),
    }));
    const ag: CmdItem[] = agents.map((a) => ({
      id: "ag-" + a.agent, label: a.label ?? a.agent, group: "agent",
      kw: a.agent + " " + (a.label ?? "") + " " + (a.task ?? "") + " " + (a.module ?? ""),
      sub: `${a.module ?? ""} · ${statusOf(a.state).label}`, clr: statusOf(a.state).clr, run: actions.goOverview,
    }));
    return [...views, ...acts, ...proj, ...ag];
  }, [projects, agents, actions, t]);

  const results = useMemo<CmdItem[]>(() => {
    if (!q.trim()) {
      const order: CmdItem["group"][] = ["view", "action", "project", "agent"];
      return [...items].sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group)).slice(0, 11);
    }
    return items
      .map((i) => ({ i, s: fuzzy(q, i.label + " " + i.kw) }))
      .filter((x) => x.s < Infinity)
      .sort((a, b) => a.s - b.s)
      .map((x) => x.i)
      .slice(0, 12);
  }, [q, items]);

  useEffect(() => { setSel((s) => Math.min(s, Math.max(0, results.length - 1))); }, [results.length]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => (s + 1) % results.length); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => (s - 1 + results.length) % results.length); }
      else if (e.key === "Enter") { e.preventDefault(); const r = results[sel]; if (r) { r.run(); onClose(); } }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, results, sel, onClose]);

  useEffect(() => {
    listRef.current?.querySelector(".cmd-item.sel")?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!open) return null;
  const groupLabel: Record<string, string> = { view: t("grp_nav"), action: t("grp_actions"), project: t("grp_projects"), agent: t("grp_fleet") };
  let lastGroup: string | null = null;

  return (
    <div className="cmd-bg" onClick={onClose}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Palette de commandes">
        <div className="cmd-search">
          {Icon.search({})}
          <input ref={inputRef} value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder={t("cmd_ph")} spellCheck={false} />
          <kbd className="cmd-esc">esc</kbd>
        </div>
        <div className="cmd-list" ref={listRef}>
          {results.length === 0 && <div className="cmd-empty">{t("cmd_none")}</div>}
          {results.map((r, idx) => {
            const head = r.group !== lastGroup ? ((lastGroup = r.group), groupLabel[r.group]) : null;
            return (
              <Fragment key={r.id}>
                {head && <div className="cmd-grp">{head}</div>}
                <div className={"cmd-item" + (idx === sel ? " sel" : "")} onMouseEnter={() => setSel(idx)} onClick={() => { r.run(); onClose(); }}>
                  <span className="cmd-ic" style={r.clr ? { color: r.clr } : undefined}>
                    {r.group === "agent"
                      ? <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", background: r.clr }} />
                      : (r.icon ? r.icon({}) : Icon.chevron({}))}
                  </span>
                  <span className="cmd-txt">
                    <span className="cmd-lbl">{r.label}</span>
                    {r.sub && <span className="cmd-sub">{r.sub}</span>}
                  </span>
                  {idx === sel && <kbd className="cmd-enter">↵</kbd>}
                </div>
              </Fragment>
            );
          })}
        </div>
        <div className="cmd-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> {t("cmd_move")}</span>
          <span><kbd>↵</kbd> {t("cmd_open")}</span>
          <span className="cmd-foot-grow" />
          <span className="cmd-brand">{Icon.bolt({ style: { width: 12, height: 12 } })} Mission Control</span>
        </div>
      </div>
    </div>
  );
}
