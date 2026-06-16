"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/mc/icons";
import { useI18n, type Lang } from "@/lib/i18n";
import type { Me } from "@/lib/api";

export type FleetCounts = { running: number; blocked: number; waiting: number; done: number };

type NavItem = { id: string; tkey: string; icon: (p?: object) => JSX.Element; count?: number };

// Catégorie « Mission Control » : les vues de pilotage/cockpit.
const MISSION: NavItem[] = [
  { id: "home", tkey: "nav_home", icon: Icon.spark },
  { id: "overview", tkey: "nav_mission", icon: Icon.grid },
  { id: "projects", tkey: "nav_projects", icon: Icon.folder },
  { id: "departments", tkey: "nav_depts", icon: Icon.layers },
  { id: "hierarchy", tkey: "nav_hierarchy", icon: Icon.layers },
  { id: "cost", tkey: "nav_cost", icon: Icon.coin },
  { id: "audit", tkey: "nav_audit", icon: Icon.gauge },
];
const WORKSPACE: NavItem[] = [{ id: "repos", tkey: "nav_repos", icon: Icon.folder }];

// Catégorie « Flotte » : les états live des agents (compteurs passés par le parent).
function fleetNav(counts: FleetCounts): NavItem[] {
  return [
    { id: "running", tkey: "nav_running", icon: Icon.pulse, count: counts.running },
    { id: "review", tkey: "nav_review", icon: Icon.alert, count: counts.blocked },
    { id: "pending", tkey: "nav_pending", icon: Icon.clock },
    { id: "queue", tkey: "nav_queue", icon: Icon.clock, count: counts.waiting },
    { id: "completed", tkey: "nav_completed", icon: Icon.check, count: counts.done },
  ];
}

// "Bonjour Mr Sultan" — civilité genrée + nom (repli sur le préfixe d'email).
function greeting(me: Me | null, t: (k: string) => string): string | null {
  if (!me) return null;
  const civ = me.civility ? t("civ_" + me.civility) : "";
  const name = me.full_name || me.email.split("@")[0];
  return `${t("hello")} ${civ} ${name}`.replace(/\s+/g, " ").trim();
}

export function Sidebar({
  view,
  onNav,
  canNew,
  onNew,
  onLogout,
  onChangePassword,
  me,
  counts,
}: {
  view: string;
  onNav: (v: string) => void;
  canNew: boolean;
  onNew: () => void;
  onLogout: () => void;
  onChangePassword: () => void;
  me: Me | null;
  counts: FleetCounts;
}) {
  const canAdmin = me?.role === "admin";
  const { t } = useI18n();
  const hello = greeting(me, t);
  const FLEET = fleetNav(counts);
  const item = (it: NavItem) => (
    <button
      key={it.id}
      className={"nav-item" + (view === it.id ? " active" : "")}
      onClick={() => onNav(it.id)}
      title={t(it.tkey)}
    >
      {it.icon({})}
      <span>{t(it.tkey)}</span>
      {it.count != null && <span className="count">{it.count}</span>}
    </button>
  );
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo brand-img"><img src="/brand-mark.png" alt="Mission Control" /></div>
        <div>
          <div className="name">Mission Control</div>
          <div className="sub">{t("brand_sub")}</div>
        </div>
      </div>
      {hello && (
        <div className="user-greet" title={me?.email}>
          <span className="user-greet-ic">{Icon.spark({})}</span>
          <span className="user-greet-txt">{hello}</span>
        </div>
      )}
      {canNew && (
        <button className="btn primary" style={{ margin: "0 4px 10px" }} onClick={onNew}>
          {Icon.plus({})} <span>{t("new_project")}</span>
        </button>
      )}
      <div className="sidebar-scroll">
        <div className="nav-label">{t("sec_mission")}</div>
        {MISSION.map(item)}
        <div className="nav-label">{t("nav_fleet")}</div>
        {FLEET.map(item)}
        <div className="nav-label">{t("sec_workspace")}</div>
        {WORKSPACE.map(item)}
        {canAdmin && (
          <>
            <div className="nav-label">{t("nav_admin")}</div>
            {item({ id: "admin", tkey: "nav_admin", icon: Icon.shield })}
          </>
        )}
      </div>
      <button className="nav-item" onClick={onChangePassword} title={t("au_change_title")}>
        {Icon.shield({})}<span>{t("au_change_title")}</span>
      </button>
      <button className="nav-item logout-item" onClick={onLogout} title={t("logout")}>
        {Icon.logout({})}<span>{t("logout")}</span>
      </button>
    </aside>
  );
}

const LANGS: { id: Lang; short: string }[] = [
  { id: "fr", short: "FR" },
  { id: "en", short: "EN" },
  { id: "ar", short: "ع" },
];

export function Topbar({
  title,
  theme,
  onToggleTheme,
  soundOn,
  onToggleSound,
  onCommand,
  onMenu,
  onBell,
  badge,
  onLogout,
  canNew,
  onNew,
}: {
  title: string;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  soundOn: boolean;
  onToggleSound: () => void;
  onCommand: () => void;
  onMenu: () => void;
  onBell: () => void;
  badge: number;
  onLogout: () => void;
  canNew: boolean;
  onNew: () => void;
}) {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="topbar">
      <button className="btn ghost icon menu-btn" onClick={onMenu} title="Menu">{Icon.menu({})}</button>
      <h1>{title}</h1>
      <div className="search" onClick={onCommand} style={{ cursor: "pointer" }}>
        {Icon.search({})}
        <input placeholder={t("search_ph")} readOnly style={{ cursor: "pointer" }} />
        <kbd>⌘K</kbd>
      </div>
      <div className="topbar-actions">
        <button className="btn ghost icon" onClick={onCommand} title="⌘K">{Icon.search({})}<kbd>⌘K</kbd></button>
        <button className="btn ghost icon notif-btn" onClick={onBell} title="Notifications">
          {Icon.bell({})}
          {badge > 0 && <span className="notif-badge">{badge}</span>}
        </button>
        <div className="lang-switch">
          {LANGS.map((l) => (
            <button key={l.id} type="button" className={"ls" + (lang === l.id ? " on" : "")} onClick={() => setLang(l.id)}>{l.short}</button>
          ))}
        </div>
        <button className="btn ghost icon" onClick={onToggleSound} title={t("a_sound")} data-on={soundOn ? "1" : "0"}>
          {soundOn ? Icon.volume({}) : Icon.mute({})}
        </button>
        <button className="btn ghost icon" onClick={onToggleTheme} title={t("a_theme")}>
          {theme === "dark" ? Icon.sun({}) : Icon.moon({})}
        </button>
        {canNew && (
          <button className="btn primary" onClick={onNew}>{Icon.plus({})} <span>{t("new_project")}</span></button>
        )}
      </div>
    </div>
  );
}

export function Shell({
  title,
  me,
  view,
  onNav,
  theme,
  onToggleTheme,
  soundOn,
  onToggleSound,
  collapsed,
  onToggleCollapse,
  canNew,
  onNew,
  onLogout,
  onChangePassword,
  onCommand,
  onBell,
  badge,
  counts,
  children,
}: {
  title: string;
  me: Me | null;
  view: string;
  onNav: (v: string) => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  soundOn: boolean;
  onToggleSound: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  canNew: boolean;
  onNew: () => void;
  onLogout: () => void;
  onChangePassword: () => void;
  onCommand: () => void;
  onBell: () => void;
  badge: number;
  counts: FleetCounts;
  children: ReactNode;
}) {
  return (
    <div className={"app" + (collapsed ? " nav-collapsed" : "")}>
      <Sidebar view={view} onNav={onNav} canNew={canNew} onNew={onNew} onLogout={onLogout} onChangePassword={onChangePassword} me={me} counts={counts} />
      <main className="main">
        <Topbar
          title={title} theme={theme} onToggleTheme={onToggleTheme} soundOn={soundOn} onToggleSound={onToggleSound} onCommand={onCommand}
          onMenu={onToggleCollapse} onBell={onBell} badge={badge} onLogout={onLogout} canNew={canNew} onNew={onNew}
        />
        <div className="scroll">{children}</div>
      </main>
    </div>
  );
}
