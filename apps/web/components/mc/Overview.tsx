"use client";

import { useState } from "react";
import type { Agent } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { fmtAge, statusOf } from "@/lib/mc";
import { Badge } from "@/components/mc/Projects";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { useI18n } from "@/lib/i18n";

function StatStrip({ agents }: { agents: Agent[] }) {
  const { t } = useI18n();
  const by = (s: string) => agents.filter((a) => a.state === s).length;
  const stats = [
    { k: t("st_active"), icon: Icon.pulse, v: by("working"), sub: "/ " + agents.length, clr: "var(--run)" },
    { k: t("st_blocked"), icon: Icon.alert, v: by("blocked") + by("error"), clr: "var(--block)" },
    { k: t("st_stale"), icon: Icon.clock, v: by("stale"), clr: "var(--wait)" },
    { k: t("st_queue"), icon: Icon.clock, v: by("idle"), clr: "var(--tx-mid)" },
    { k: t("st_done"), icon: Icon.check, v: by("done"), clr: "var(--done)" },
  ];
  return (
    <div className="stat-strip">
      {stats.map((s, i) => (
        <div className="stat" key={i}>
          <div className="k">{s.icon({})}{s.k}</div>
          <div className="v num" style={{ color: s.clr }}>{s.v}{s.sub && <small> {s.sub}</small>}</div>
        </div>
      ))}
    </div>
  );
}

function AgentCard({ agent, onOpen }: { agent: Agent; onOpen: () => void }) {
  const s = statusOf(agent.state);
  const pct = agent.state === "done" ? 100 : agent.progress;
  return (
    <div className="card" onClick={onOpen} style={{ cursor: "pointer" }}>
      <div className="top">
        <span className="card-bot" style={{ color: s.clr }}>
          <Ant state={antStateOf(agent.state)} color={s.clr} size={32} />
        </span>
        <div className="card-id">
          <div className="name">{agent.label ?? agent.agent}</div>
          <div className="repo">
            {agent.module ?? "—"}{agent.branch ? ` · ${agent.branch}` : ""}
          </div>
        </div>
        <Badge state={agent.state} />
      </div>
      <div className="task">{agent.state === "blocked" && agent.blocker ? `⛔ ${agent.blocker}` : agent.task ?? "—"}</div>
      <div className="prog">
        <div className="prog-bar"><i style={{ width: pct + "%", background: s.clr }} /></div>
        <div className="prog-meta">
          <span className="step">{agent.tasks_total ? `${agent.tasks_done ?? 0}/${agent.tasks_total}` : ""}</span>
          <span className="pct num">{pct}%</span>
        </div>
      </div>
      <div className="foot">
        <span className="m">{Icon.clock({})}<b>{fmtAge(agent.age_seconds)}</b></span>
        {agent.module && <span className="m">{Icon.layers({})}<b>{agent.module}</b></span>}
      </div>
    </div>
  );
}

const FILTERS = ["all", "working", "blocked", "stale", "idle", "done"] as const;
type Filter = (typeof FILTERS)[number];
const FILTER_KEY: Record<Filter, string> = {
  all: "f_all", working: "f_working", blocked: "f_blocked", stale: "f_stale", idle: "f_idle", done: "f_done",
};

export function Overview({ agents, onOpenAgent }: { agents: Agent[]; onOpenAgent: (a: Agent) => void }) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<Filter>("all");
  const match = (a: Agent) =>
    filter === "all" ? true : filter === "blocked" ? a.state === "blocked" || a.state === "error" : a.state === filter;
  const shown = agents.filter(match);
  const n = (f: Filter) => agents.filter((a) => (f === "all" ? true : f === "blocked" ? a.state === "blocked" || a.state === "error" : a.state === f)).length;

  return (
    <div className="pj-page">
      <StatStrip agents={agents} />
      <div className="section-head">
        <h2>{t("nav_fleet")}</h2>
        <span className="hint">{agents.length} {t("u_agents")}</span>
        <div className="filters">
          {FILTERS.map((f) => (
            <button key={f} className={"chip" + (filter === f ? " active" : "")} onClick={() => setFilter(f)}>
              {t(FILTER_KEY[f])} <span className="n num">{n(f)}</span>
            </button>
          ))}
        </div>
      </div>
      {shown.length ? (
        <div className="grid">
          {shown.map((a) => <AgentCard key={a.agent} agent={a} onOpen={() => onOpenAgent(a)} />)}
        </div>
      ) : (
        <div style={{ padding: "40px 0", textAlign: "center", color: "var(--tx-lo)", fontSize: 13 }}>{t("none_here")}</div>
      )}
    </div>
  );
}
