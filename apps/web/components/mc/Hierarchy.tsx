"use client";

import { useState } from "react";
import { getProject, type Agent, type ProjectDetail, type ProjectSummary } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { useI18n } from "@/lib/i18n";
import { completionColor, monogram, statusOf } from "@/lib/mc";

function AgentLeaf({ agent, onOpen }: { agent: Agent; onOpen: () => void }) {
  const s = statusOf(agent.state);
  const pct = agent.state === "done" ? 100 : agent.progress;
  return (
    <div className="tleaf" onClick={onOpen} style={{ cursor: "pointer" }}>
      <span style={{ color: s.clr, flex: "none", width: 22, height: 22 }}><Ant state={antStateOf(agent.state)} color={s.clr} size={22} /></span>
      <span className="tname">{agent.label ?? agent.agent}</span>
      <span className="tsub">{agent.module ?? ""}</span>
      <span className="tspacer" style={{ flex: 1 }} />
      <span className="tbar"><i style={{ width: pct + "%", background: s.clr }} /></span>
      <span className="num" style={{ fontSize: 11, color: s.clr, width: 34, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

function ProjectNode({
  p,
  onOpenProject,
  onOpenAgent,
}: {
  p: ProjectSummary;
  onOpenProject: (id: string) => void;
  onOpenAgent: (a: Agent) => void;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const hue = completionColor(p.progress / 100);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      try { setDetail(await getProject(p.id)); } catch { /* */ } finally { setLoading(false); }
    }
  };

  return (
    <div className="tnode">
      <div className="trow" onClick={toggle}>
        <span className={"tchev" + (open ? " open" : "")}>{Icon.chevron({})}</span>
        <span className="tglyph" style={{ background: hue }}>{monogram(p.name)}</span>
        <span>
          <span className="tname">{p.name}</span>
          <div className="tsub">{p.agents_total} agents · {p.tasks_done}/{p.tasks_total} · {p.status}</div>
        </span>
        <span className="tspacer" style={{ flex: 1 }} />
        <span className="tcount" style={{ color: hue }}>{p.progress}%</span>
        <span
          role="button"
          onClick={(e) => { e.stopPropagation(); onOpenProject(p.id); }}
          className="tcount"
          style={{ cursor: "pointer" }}
          title="Ouvrir le projet"
        >
          {Icon.folder({ style: { width: 13, height: 13 } })}
        </span>
      </div>
      {open && (
        <div className="tchildren">
          {loading && <div className="tsub">…</div>}
          {detail && detail.agents.length === 0 && <div className="tsub">—</div>}
          {detail?.agents.map((a) => <AgentLeaf key={a.agent} agent={a} onOpen={() => onOpenAgent(a)} />)}
        </div>
      )}
    </div>
  );
}

export function Hierarchy({
  projects,
  onOpenProject,
  onOpenAgent,
}: {
  projects: ProjectSummary[];
  onOpenProject: (id: string) => void;
  onOpenAgent: (a: Agent) => void;
}) {
  const { t } = useI18n();
  const totalAgents = projects.reduce((s, p) => s + p.agents_total, 0);
  return (
    <div className="pj-page">
      <div className="tree">
        <div className="tnode root">
          <div className="trow" style={{ cursor: "default" }}>
            <span className="tglyph brand-img" style={{ background: "#1b1a1f", padding: 4 }}>
              <img src="/brand-mark.png" alt="" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            </span>
            <span>
              <span className="tname">Mission Control</span>
              <div className="tsub">{projects.length} {t("nav_projects").toLowerCase()} · {totalAgents} {t("u_agents")}</div>
            </span>
          </div>
        </div>
        {projects.map((p) => (
          <ProjectNode key={p.id} p={p} onOpenProject={onOpenProject} onOpenAgent={onOpenAgent} />
        ))}
      </div>
    </div>
  );
}
