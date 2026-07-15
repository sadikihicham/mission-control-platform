// @ts-nocheck
"use client";

// Depts.tsx — vue « organigramme » : regroupement live des agents par module.
// Il n'existe aucune notion de département/équipe côté backend : cette vue
// regroupe simplement les agents réels (GET /agents) par leur champ `module`,
// sans organigramme figé ni coût — voir CLAUDE.md / CONTRACTS.md.

import { useEffect, useState } from "react";
import { Icon } from "@/components/mc/icons";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { Robot, robotRoleLabel, robotActivityOf } from "@/components/mc/Robot";
import { getAgents, type Agent } from "@/lib/api";
import { statusOf, bucketOf, healthFrom, HEALTH_META, HEALTH_ORDER, fmtAge } from "@/lib/mc";
import { useI18n } from "@/lib/i18n";

// Shared i18n table (module-level) — used by every sub-component via useI18n.
const TR = {
  fr: {
    org_chart: "Organigramme",
    agents: "agents",
    agent: "agent",
    idle: "inactif",
    to_review: "À valider",
    agents_title: "Agents",
    running: "en cours",
    no_agent: "Aucun agent dans ce groupe.",
    tasks_go: "Tâches",
    open_agent: "Ouvrir l'agent",
    tasks: "Tâches",
    departments: "Départements",
    unassigned: "Non assigné",
    not_tracked: "Non suivi côté serveur",
  },
  en: {
    org_chart: "Org chart",
    agents: "agents",
    agent: "agent",
    idle: "idle",
    to_review: "To review",
    agents_title: "Agents",
    running: "running",
    no_agent: "No agent in this group.",
    tasks_go: "Tasks",
    open_agent: "Open agent",
    tasks: "Tasks",
    departments: "Departments",
    unassigned: "Unassigned",
    not_tracked: "Not tracked server-side",
  },
  ar: {
    org_chart: "الهيكل التنظيمي",
    agents: "وكلاء",
    agent: "وكيل",
    idle: "خامل",
    to_review: "للمراجعة",
    agents_title: "الوكلاء",
    running: "قيد التشغيل",
    no_agent: "لا يوجد وكيل في هذه المجموعة.",
    tasks_go: "المهام",
    open_agent: "فتح الوكيل",
    tasks: "المهام",
    departments: "الأقسام",
    unassigned: "غير مسند",
    not_tracked: "غير متتبَّع على الخادم",
  },
};

// clé de regroupement pour les agents sans module renseigné
const UNASSIGNED = "__unassigned__";

// palette fixe + hash de chaîne : couleur stable par module, sans liste figée
const HUES = ["#d97757", "#3fb6a8", "#6b8cff", "#e0a23f", "#b07ae8", "#5bb0e8", "#e0567a", "#8b93a7"];
function hueFor(key) {
  let h = 0;
  for (const c of key) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length];
}

function groupsOf(agents) {
  const map = new Map();
  for (const a of agents) {
    const key = a.module && a.module.trim() ? a.module : UNASSIGNED;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(a);
  }
  return Array.from(map.entries()).map(([key, items]) => ({ key, items }));
}

function groupLabel(key, tt) {
  return key === UNASSIGNED ? tt("unassigned") : key;
}

// ---------- Level 1: org diagram (grille plate des groupes) ----------
function OrgDiagram({ agents, onPick }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  // groupes triés : ceux avec des agents bloqués d'abord, puis par activité (running+blocked)
  const groups = groupsOf(agents)
    .map((g) => {
      const c = healthFrom(g.items);
      return { ...g, score: c.blocked * 100 + (c.running + c.blocked) };
    })
    .sort((a, b) => b.score - a.score);
  return (
    <div className="org">
      <div className="org-head">
        <div className="eyebrow2">
          {Icon.layers({})} {tt("org_chart")}
        </div>
      </div>
      <div className="org-grid">
        {groups.map((g) => (
          <GroupNode key={g.key} groupKey={g.key} items={g.items} onPick={onPick} />
        ))}
      </div>
    </div>
  );
}

function GroupNode({ groupKey, items, onPick }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const c = healthFrom(items);
  const live = c.running + c.blocked;
  const hue = hueFor(groupKey);
  const label = groupLabel(groupKey, tt);
  return (
    <button
      className={"dept-node" + (c.blocked ? " alerted" : "")}
      style={{ "--dh": hue }}
      onClick={() => onPick({ key: groupKey, items })}
    >
      {c.blocked > 0 && (
        <span className="dept-alert">
          {Icon.alert({})}
          {c.blocked}
        </span>
      )}
      <div className="dept-top">
        <span className="dept-glyph">{Icon.layers({})}</span>
        <div className="dept-id">
          <div className="dept-nm">{label}</div>
          <div className="dept-meta">
            {items.length + " " + (items.length > 1 ? tt("agents") : tt("agent"))}
          </div>
        </div>
        {live > 0 && (
          <span className="equalizer live" style={{ "--clr": "var(--run)" }}>
            {[0, 1, 2, 3, 4].map((i) => (
              <span className="eq-bar" key={i}></span>
            ))}
          </span>
        )}
      </div>
      <div className="dept-ants">
        {items.map((a) => (
          <span className="dept-ant" key={a.agent} style={{ color: statusOf(a.state).clr }}>
            <Ant state={antStateOf(a.state)} color={statusOf(a.state).clr} size={26} />
          </span>
        ))}
      </div>
      <div className="dept-kpis">
        <span className="dept-kpi">
          {Icon.coin({})}
          <b className="num" title={tt("not_tracked")}>—</b>
        </span>
        <span className={"dept-kpi" + (c.blocked ? " warn" : "")}>
          {Icon.alert({})}
          <b className="num">{c.blocked}</b> {tt("to_review")}
        </span>
      </div>
      <div className="dept-health">
        {HEALTH_ORDER.map((k) =>
          c[k] ? <i key={k} style={{ flex: c[k], background: HEALTH_META[k].clr }}></i> : null
        )}
      </div>
    </button>
  );
}

// ---------- Level 2: group agents ----------
function DeptAgents({ dept, onAgent }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const items = [...dept.items].sort(
    (a, b) => HEALTH_ORDER.indexOf(bucketOf(a.state)) - HEALTH_ORDER.indexOf(bucketOf(b.state))
  );
  const h = healthFrom(items);
  return (
    <div className="dpa">
      <div className="section-head">
        <h2>
          {Icon.layers({})} {tt("agents_title")}
        </h2>
        <span className="hint">
          {items.length} · {h.running} {tt("running")}
        </span>
      </div>
      <div className="dpa-grid">
        {items.length === 0 && <div className="dp-empty">{tt("no_agent")}</div>}
        {items.map((a) => {
          const s = statusOf(a.state);
          const bucket = bucketOf(a.state);
          const act = bucket === "running" ? robotActivityOf(a) : null;
          return (
            <button
              className={"dpa-card s-" + bucket}
              key={a.agent}
              style={{ "--clr": s.clr }}
              onClick={() => onAgent(a)}
            >
              <div className="dpa-top">
                <span className="dpa-bot" style={{ color: s.clr }}>
                  <Ant state={antStateOf(a.state)} color={s.clr} size={34} />
                </span>
                <div className="dpa-id">
                  <div className="nm">{a.label || a.agent}</div>
                  <div className="ds">
                    {robotRoleLabel(a.module)} · {a.branch || "—"}
                  </div>
                </div>
                <span className={"badge " + s.badge}>
                  <span className="dot" /> {s.label}
                </span>
              </div>
              {act && (
                <div className={"act-tag act-" + act}>
                  <span className="act-pulse" style={{ background: s.clr }}></span>
                  <span className="act-bot" style={{ color: s.clr }}>
                    <Robot role={a.module} color={s.clr} size={18} status={bucket} activity={act} />
                  </span>
                  {act}
                </div>
              )}
              <div className="dpa-task">{a.task || "—"}</div>
              <div className="dpa-foot">
                <span className="dpa-prog">
                  <span className="bar">
                    <i
                      style={{
                        width: (a.state === "done" ? 100 : a.progress) + "%",
                        background: s.clr,
                      }}
                    ></i>
                  </span>
                  {!!a.tasks_total && (
                    <span className="num">
                      {a.tasks_done ?? 0}/{a.tasks_total}
                    </span>
                  )}
                </span>
                <span className="num dpa-cost" title={tt("not_tracked")}>—</span>
                <span className="dpa-go">{tt("tasks_go")} {Icon.chevron({})}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Level 3: agent detail (résumé réel, sans checklist fictive) ----------
function AgentTasks({ agent, onOpenAgent }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const s = statusOf(agent.state);
  const bucket = bucketOf(agent.state);
  return (
    <div className="dpt">
      <div className="dpt-hero" style={{ "--clr": s.clr }}>
        <span className="dpt-bot" style={{ color: s.clr }}>
          <Robot
            role={agent.module}
            color={s.clr}
            size={54}
            status={bucket}
            activity={bucket === "running" ? robotActivityOf(agent) : null}
          />
        </span>
        <div className="dpt-id">
          <div className="nm">{agent.label || agent.agent}</div>
          <div className="ds">
            {robotRoleLabel(agent.module)} · {agent.branch || "—"}
          </div>
          <div className="dpt-tags">
            <span className={"badge " + s.badge}>
              <span className="dot" /> {s.label}
            </span>
            <span className="dpt-tag">
              {Icon.clock({})}
              {fmtAge(agent.age_seconds)}
            </span>
          </div>
        </div>
        <button className="dpt-open btn primary" onClick={() => onOpenAgent(agent)}>
          {Icon.terminal({})} {tt("open_agent")}
        </button>
      </div>
      <div className="section-head">
        <h2>
          {Icon.sliders({})} {tt("tasks")}
        </h2>
      </div>
      <div className="dpt-tags">
        <span className="dpt-tag">
          {Icon.terminal({})} {agent.task || "—"}
        </span>
        <span className="dpt-tag">
          {Icon.pr({})} {agent.branch || "—"}
        </span>
        {agent.blocker && (
          <span
            className="dpt-tag"
            style={{ color: "var(--block)", background: "color-mix(in oklab, var(--block) 18%, var(--bg-3))" }}
          >
            {Icon.alert({})} {agent.blocker}
          </span>
        )}
        <span className="dpt-tag">
          {Icon.gauge({})} {agent.progress}%
        </span>
      </div>
    </div>
  );
}

export function Depts({ onOpenAgent = () => {} }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const [agents, setAgents] = useState<Agent[]>([]);
  useEffect(() => {
    let on = true;
    getAgents().then((a) => on && setAgents(a || [])).catch(() => {});
    return () => { on = false; };
  }, []);
  const [dept, setDept] = useState(null);
  const [agent, setAgent] = useState(null);
  const crumb = (
    <div className="dp-crumb">
      <button
        onClick={() => {
          setDept(null);
          setAgent(null);
        }}
      >
        {tt("departments")}
      </button>
      {dept && (
        <>
          {Icon.chevron({})}
          <button onClick={() => setAgent(null)} className={!agent ? "cur" : ""}>
            {groupLabel(dept.key, tt)}
          </button>
        </>
      )}
      {agent && (
        <>
          {Icon.chevron({})}
          <span className="cur">{agent.label || agent.agent}</span>
        </>
      )}
    </div>
  );
  return (
    <div className="depts">
      {(dept || agent) && crumb}
      <div className="dp-stage" key={agent ? "t" : dept ? "a" : "o"}>
        {!dept && <OrgDiagram agents={agents} onPick={setDept} />}
        {dept && !agent && <DeptAgents dept={dept} onAgent={setAgent} />}
        {agent && <AgentTasks agent={agent} onOpenAgent={onOpenAgent} />}
      </div>
    </div>
  );
}
