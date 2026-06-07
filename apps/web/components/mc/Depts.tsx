"use client";
// @ts-nocheck

// Depts.tsx — Departments org view: company structure → agents → tasks.
// Porté depuis le design mc-depts.jsx (rendu statique sur les données mock).

import { useState } from "react";
import { AGENTS, STATUS, fmtCost, fmtDur } from "@/lib/mc-data";
import { Icon } from "@/components/mc/icons";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { Robot, robotRoleLabel, robotActivityOf } from "@/components/mc/Robot";
import { useI18n } from "@/lib/i18n";

const DeI = Icon;

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
    no_agent: "Aucun agent dans ce département.",
    tasks_go: "Tâches",
    open_agent: "Ouvrir l'agent",
    tasks: "Tâches",
    awaiting_review: "En attente de validation",
    departments: "Départements",
    // department names
    dept_dg: "Direction",
    dept_finance: "Finance",
    dept_ventes: "Ventes",
    dept_marketing: "Marketing",
    dept_hr: "Ressources humaines",
    dept_achats: "Achats",
    dept_logistique: "Logistique",
    dept_stock: "Stock",
  },
  en: {
    org_chart: "Org chart",
    agents: "agents",
    agent: "agent",
    idle: "idle",
    to_review: "To review",
    agents_title: "Agents",
    running: "running",
    no_agent: "No agent in this department.",
    tasks_go: "Tasks",
    open_agent: "Open agent",
    tasks: "Tasks",
    awaiting_review: "Awaiting review",
    departments: "Departments",
    dept_dg: "Executive",
    dept_finance: "Finance",
    dept_ventes: "Sales",
    dept_marketing: "Marketing",
    dept_hr: "Human Resources",
    dept_achats: "Procurement",
    dept_logistique: "Logistics",
    dept_stock: "Inventory",
  },
  ar: {
    org_chart: "الهيكل التنظيمي",
    agents: "وكلاء",
    agent: "وكيل",
    idle: "خامل",
    to_review: "للمراجعة",
    agents_title: "الوكلاء",
    running: "قيد التشغيل",
    no_agent: "لا يوجد وكيل في هذا القسم.",
    tasks_go: "المهام",
    open_agent: "فتح الوكيل",
    tasks: "المهام",
    awaiting_review: "بانتظار المراجعة",
    departments: "الأقسام",
    dept_dg: "الإدارة التنفيذية",
    dept_finance: "المالية",
    dept_ventes: "المبيعات",
    dept_marketing: "التسويق",
    dept_hr: "الموارد البشرية",
    dept_achats: "المشتريات",
    dept_logistique: "اللوجستيات",
    dept_stock: "المخزون",
  },
};

// department definitions + which agents belong to each
const DEPTS = [
  { id: "dg",          label: "Executive",       icon: DeI.spark,  hue: "#d97757", agents: ["a-perf", "a-docs"] },
  { id: "finance",     label: "Finance",         icon: DeI.coin,   hue: "#3fb6a8", agents: ["a-checkout", "a-tests"] },
  { id: "ventes",      label: "Sales",           icon: DeI.pulse,  hue: "#6b8cff", agents: ["a-react", "a-dark"] },
  { id: "marketing",   label: "Marketing",       icon: DeI.bolt,   hue: "#e0a23f", agents: ["a-i18n", "a-images"] },
  { id: "hr",          label: "Human Resources", icon: DeI.layers, hue: "#b07ae8", agents: ["a-sec", "a-auth"] },
  { id: "achats",      label: "Procurement",     icon: DeI.folder, hue: "#5bb0e8", agents: ["a-migrate"] },
  { id: "logistique",  label: "Logistics",       icon: DeI.pr,     hue: "#e0567a", agents: ["a-ci"] },
  { id: "stock",       label: "Inventory",       icon: DeI.layers, hue: "#8b93a7", agents: [] },
];
const STORD = ["blocked", "running", "waiting", "done"];

function deptAgents(dept, agents) {
  const byId = Object.fromEntries(agents.map((a) => [a.id, a]));
  return dept.agents.map((id) => byId[id]).filter(Boolean);
}
function counts(items) {
  const c = { running: 0, waiting: 0, blocked: 0, done: 0 };
  items.forEach((a) => c[a.status]++);
  return c;
}
function deptCost(items) {
  return items.reduce((s, a) => s + a.cost, 0);
}

// translated department label, falls back to the static label
function deptLabel(dept, tt) {
  return tt("dept_" + dept.id);
}

// ---------- Level 1: org diagram ----------
function OrgDiagram({ agents, onPick }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const dg = DEPTS[0];
  // departments (excl. DG) ordered: those with blocked agents first, then by live activity
  const others = DEPTS.slice(1)
    .map((d) => {
      const it = deptAgents(d, agents);
      const c = counts(it);
      return { d, score: c.blocked * 100 + (c.running + c.blocked) };
    })
    .sort((a, b) => b.score - a.score)
    .map((x) => x.d);
  return (
    <div className="org">
      <div className="org-head">
        <div className="eyebrow2">
          {DeI.layers({})} {tt("org_chart")}
        </div>
      </div>

      <div className="org-top">
        <DeptNode dept={dg} agents={agents} onPick={onPick} big />
      </div>
      <div className="org-spine">
        <span className="org-spine-dot"></span>
      </div>
      <div className="org-grid">
        {others.map((d) => (
          <DeptNode key={d.id} dept={d} agents={agents} onPick={onPick} />
        ))}
      </div>
    </div>
  );
}

function DeptNode({ dept, agents, onPick, big }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const items = deptAgents(dept, agents);
  const c = counts(items);
  const live = c.running + c.blocked;
  const cost = deptCost(items);
  return (
    <button
      className={
        "dept-node" +
        (big ? " big" : "") +
        (items.length ? "" : " idle") +
        (c.blocked ? " alerted" : "")
      }
      style={{ "--dh": dept.hue }}
      onClick={() => onPick(dept)}
    >
      {c.blocked > 0 && (
        <span className="dept-alert">
          {DeI.alert({})}
          {c.blocked}
        </span>
      )}
      <div className="dept-top">
        <span className="dept-glyph">{dept.icon({})}</span>
        <div className="dept-id">
          <div className="dept-nm">{deptLabel(dept, tt)}</div>
          <div className="dept-meta">
            {items.length
              ? items.length + " " + (items.length > 1 ? tt("agents") : tt("agent"))
              : tt("idle")}
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
      {items.length > 0 && (
        <>
          <div className="dept-ants">
            {items.map((a) => (
              <span className="dept-ant" key={a.id} style={{ color: STATUS[a.status].clr }}>
                <Ant state={antStateOf(a.status)} color={STATUS[a.status].clr} size={big ? 30 : 26} />
              </span>
            ))}
          </div>
          <div className="dept-kpis">
            <span className="dept-kpi">
              {DeI.coin({})}
              <b className="num">{fmtCost(cost)}</b>
            </span>
            <span className={"dept-kpi" + (c.blocked ? " warn" : "")}>
              {DeI.alert({})}
              <b className="num">{c.blocked}</b> {tt("to_review")}
            </span>
          </div>
          <div className="dept-health">
            {STORD.map((k) =>
              c[k] ? <i key={k} style={{ flex: c[k], background: STATUS[k].clr }}></i> : null
            )}
          </div>
        </>
      )}
    </button>
  );
}

// ---------- Level 2: department agents ----------
function DeptAgents({ dept, agents, onAgent }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const items = deptAgents(dept, agents).sort(
    (a, b) => STORD.indexOf(a.status) - STORD.indexOf(b.status)
  );
  return (
    <div className="dpa">
      <div className="section-head">
        <h2>
          {dept.icon({})} {tt("agents_title")}
        </h2>
        <span className="hint">
          {items.length} · {counts(items).running} {tt("running")}
        </span>
      </div>
      <div className="dpa-grid">
        {items.length === 0 && <div className="dp-empty">{tt("no_agent")}</div>}
        {items.map((a) => {
          const s = STATUS[a.status];
          const done = (a.steps || []).filter((t) => t.done).length;
          const total = (a.steps || []).length;
          const act = a.status === "running" ? robotActivityOf(a) : null;
          return (
            <button
              className={"dpa-card s-" + a.status}
              key={a.id}
              style={{ "--clr": s.clr }}
              onClick={() => onAgent(a)}
            >
              <div className="dpa-top">
                <span className="dpa-bot" style={{ color: s.clr }}>
                  <Ant state={antStateOf(a.status)} color={s.clr} size={34} />
                </span>
                <div className="dpa-id">
                  <div className="nm">{a.name}</div>
                  <div className="ds">
                    {robotRoleLabel(a.role)} · {a.repo}
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
                    <Robot role={a.role} color={s.clr} size={18} status="running" activity={act} />
                  </span>
                  {act}
                </div>
              )}
              <div className="dpa-task">{a.task}</div>
              <div className="dpa-foot">
                <span className="dpa-prog">
                  <span className="bar">
                    <i
                      style={{
                        width: (a.status === "done" ? 100 : a.progress) + "%",
                        background: s.clr,
                      }}
                    ></i>
                  </span>
                  {total > 0 && (
                    <span className="num">
                      {done}/{total}
                    </span>
                  )}
                </span>
                <span className="num dpa-cost">{fmtCost(a.cost)}</span>
                <span className="dpa-go">{tt("tasks_go")} {DeI.chevron({})}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------- Level 3: agent tasks ----------
function AgentTasks({ agent, onOpenAgent }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const s = STATUS[agent.status];
  const steps = agent.steps || [];
  const TSTATE = { done: "happy", active: "working", blocked: "searching" };
  const stateOf = (st) =>
    st.blocked ? "blocked" : st.active ? "active" : st.done ? "done" : "todo";
  return (
    <div className="dpt">
      <div className="dpt-hero" style={{ "--clr": s.clr }}>
        <span className="dpt-bot" style={{ color: s.clr }}>
          <Robot
            role={agent.role}
            color={s.clr}
            size={54}
            status={agent.status}
            activity={agent.status === "running" ? robotActivityOf(agent) : null}
          />
        </span>
        <div className="dpt-id">
          <div className="nm">{agent.name}</div>
          <div className="ds">
            {robotRoleLabel(agent.role)} · {agent.repo}
          </div>
          <div className="dpt-tags">
            <span className={"badge " + s.badge}>
              <span className="dot" /> {s.label}
            </span>
            <span className="dpt-tag">
              {DeI.clock({})}
              {fmtDur(agent.status === "done" ? agent.finishedMin : agent.startedMin)}
            </span>
            <span className="dpt-tag">
              {DeI.coin({})}
              {fmtCost(agent.cost)}
            </span>
          </div>
        </div>
        <button className="dpt-open btn primary" onClick={() => onOpenAgent(agent)}>
          {DeI.terminal({})} {tt("open_agent")}
        </button>
      </div>
      <div className="section-head">
        <h2>
          {DeI.sliders({})} {tt("tasks")}
        </h2>
        <span className="hint">
          {steps.filter((x) => x.done).length}/{steps.length}
        </span>
      </div>
      <div className="dpt-tasks">
        {steps.map((st, i) => {
          const stt = stateOf(st);
          const aSt = TSTATE[stt] || "sleeping";
          const aClr =
            stt === "done"
              ? "var(--done)"
              : stt === "active"
              ? "var(--run)"
              : stt === "blocked"
              ? "var(--block)"
              : "var(--tx-dim)";
          return (
            <div className={"dpt-task st-" + stt} key={i} style={{ "--tc": aClr }}>
              <span className="dpt-task-ant" style={{ color: aClr }}>
                <Ant state={aSt} color={aClr} size={28} />
              </span>
              <span className="dpt-task-lbl">{st.label}</span>
              {stt === "active" && <span className="dpt-task-now num">{agent.step}…</span>}
              {stt === "blocked" && (
                <span className="dpt-task-now" style={{ color: "var(--block)" }}>
                  {tt("awaiting_review")}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Depts({ onOpenAgent = () => {} }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const [dept, setDept] = useState(null);
  const [agent, setAgent] = useState(null);
  const agents = AGENTS;
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
          {DeI.chevron({})}
          <button onClick={() => setAgent(null)} className={!agent ? "cur" : ""}>
            {deptLabel(dept, tt)}
          </button>
        </>
      )}
      {agent && (
        <>
          {DeI.chevron({})}
          <span className="cur">{agent.name}</span>
        </>
      )}
    </div>
  );
  return (
    <div className="depts">
      {(dept || agent) && crumb}
      <div className="dp-stage" key={agent ? "t" : dept ? "a" : "o"}>
        {!dept && <OrgDiagram agents={agents} onPick={setDept} />}
        {dept && !agent && <DeptAgents dept={dept} agents={agents} onAgent={setAgent} />}
        {agent && <AgentTasks agent={agent} onOpenAgent={onOpenAgent} />}
      </div>
    </div>
  );
}
