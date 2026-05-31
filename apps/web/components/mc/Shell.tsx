"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/mc/icons";
import { useI18n, type Lang } from "@/lib/i18n";

type Counts = { running: number; blocked: number; waiting: number };

export function Sidebar({
  view,
  onNav,
  counts,
  canNew,
  onNew,
  onLogout,
}: {
  view: string;
  onNav: (v: string) => void;
  counts: Counts;
  canNew: boolean;
  onNew: () => void;
  onLogout: () => void;
}) {
  const { t } = useI18n();
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo brand-img"><img src="/brand-mark.png" alt="Mission Control" /></div>
        <div>
          <div className="name">Mission Control</div>
          <div className="sub">Ops console</div>
        </div>
      </div>
      {canNew && (
        <button className="btn primary" style={{ margin: "0 4px 8px" }} onClick={onNew}>
          {Icon.plus({})} {t("new_project")}
        </button>
      )}
      <div className="nav-label">{t("nav_fleet")}</div>
      <button className={"nav-item" + (view === "projects" ? " active" : "")} onClick={() => onNav("projects")}>{Icon.folder({})}<span>{t("nav_projects")}</span></button>
      <button className={"nav-item" + (view === "overview" ? " active" : "")} onClick={() => onNav("overview")}>{Icon.grid({})}<span>{t("nav_overview")}</span></button>
      <button className={"nav-item" + (view === "hierarchy" ? " active" : "")} onClick={() => onNav("hierarchy")}>{Icon.layers({})}<span>{t("nav_hierarchy")}</span></button>
      <button className="nav-item" disabled style={{ opacity: 0.45 }}>{Icon.gauge({})}<span>{t("nav_audit")}</span></button>
      <div className="spacer" />
      <div className="fleet-mini">
        <div className="row"><span className="dot" style={{ background: "var(--run)" }} />{t("mini_active")} <b>{counts.running}</b></div>
        <div className="row"><span className="dot" style={{ background: "var(--block)" }} />{t("mini_blocked")} <b>{counts.blocked}</b></div>
        <div className="row"><span className="dot" style={{ background: "var(--wait)" }} />{t("mini_waiting")} <b>{counts.waiting}</b></div>
      </div>
      <button className="nav-item logout-item" onClick={onLogout}>{Icon.logout({})}<span>{t("logout")}</span></button>
    </aside>
  );
}

const LANG_LABEL: Record<Lang, string> = { fr: "FR", en: "EN", ar: "ع" };
const LANG_NEXT: Record<Lang, Lang> = { fr: "en", en: "ar", ar: "fr" };

export function Topbar({
  title,
  role,
  live,
  theme,
  onToggleTheme,
  onCommand,
  onTweaks,
}: {
  title: string;
  role: string | null;
  live: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onCommand: () => void;
  onTweaks: () => void;
}) {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="topbar">
      <h1>{title}</h1>
      <div className="search" onClick={onCommand} style={{ cursor: "pointer" }}>
        {Icon.search({})}
        <input placeholder={t("search_ph")} readOnly style={{ cursor: "pointer" }} />
        <kbd>⌘K</kbd>
      </div>
      <span className={"live-chip" + (live ? "" : " off")}>
        <span className="ldot" style={live ? { animation: "pulse 1.6s infinite" } : {}} />
        {live ? t("live") : t("polling")}
      </span>
      <button className="btn ghost icon" onClick={() => setLang(LANG_NEXT[lang])} title={t("lang")} style={{ fontWeight: 600, fontSize: 12 }}>
        {LANG_LABEL[lang]}
      </button>
      <button className="btn ghost icon" onClick={onToggleTheme} title={t("a_theme")}>
        {theme === "dark" ? Icon.sun({}) : Icon.moon({})}
      </button>
      <button className="btn ghost icon" onClick={onTweaks} title={t("tw_title")}>
        {Icon.sliders({})}
      </button>
      {role && <span className="role-chip">{role}</span>}
    </div>
  );
}

export function Shell({
  title,
  view,
  onNav,
  role,
  live,
  theme,
  onToggleTheme,
  counts,
  canNew,
  onNew,
  onLogout,
  onCommand,
  onTweaks,
  children,
}: {
  title: string;
  view: string;
  onNav: (v: string) => void;
  role: string | null;
  live: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  counts: Counts;
  canNew: boolean;
  onNew: () => void;
  onLogout: () => void;
  onCommand: () => void;
  onTweaks: () => void;
  children: ReactNode;
}) {
  return (
    <div className="app">
      <Sidebar view={view} onNav={onNav} counts={counts} canNew={canNew} onNew={onNew} onLogout={onLogout} />
      <main className="main">
        <Topbar title={title} role={role} live={live} theme={theme} onToggleTheme={onToggleTheme} onCommand={onCommand} onTweaks={onTweaks} />
        <div className="scroll">{children}</div>
      </main>
    </div>
  );
}
