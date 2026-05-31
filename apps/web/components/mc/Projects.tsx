"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { getProjectGit, type Agent, type GitInfo, type ProjectDetail, type ProjectSummary, type Task } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { useI18n } from "@/lib/i18n";
import {
  HEALTH_META,
  HEALTH_ORDER,
  type HealthCounts,
  completionColor,
  fmtAge,
  healthFrom,
  monogram,
  statusOf,
} from "@/lib/mc";

/* ---- anneau de complétion ---- */
export function PjRing({ ratio, pct, size = 50, sw = 4 }: { ratio: number; pct: number; size?: number; sw?: number }) {
  const r = size / 2 - sw - 0.5;
  const c = 2 * Math.PI * r;
  return (
    <div className="pj-ring" style={{ width: size, height: size }} title={pct + " %"}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-3)" strokeWidth={sw} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--hue)" strokeWidth={sw} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - ratio)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset .6s ease" }}
        />
      </svg>
      <span className="pj-ring-v num" style={{ color: "var(--hue)", fontSize: size > 70 ? 19 : 13 }}>
        {pct}<small>%</small>
      </span>
    </div>
  );
}

/* ---- barre de santé segmentée ---- */
export function HealthBar({ counts }: { counts: HealthCounts }) {
  return (
    <div className="pj-health">
      <div className="pj-health-bar">
        {HEALTH_ORDER.map((k) => (counts[k] ? <i key={k} style={{ flex: counts[k], background: HEALTH_META[k].clr }} /> : null))}
      </div>
      <div className="pj-health-legend">
        {HEALTH_ORDER.map((k) =>
          counts[k] ? (
            <span key={k} className="hl">
              <span className="d" style={{ background: HEALTH_META[k].clr }} />
              {counts[k]} {HEALTH_META[k].label}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}

export function Badge({ state }: { state: string }) {
  const s = statusOf(state);
  return (
    <span className={"badge " + s.badge}>
      <span className="dot" />
      {s.label}
    </span>
  );
}

/* ---- carte projet (atlas) ---- */
export function ProjectCard({
  p,
  onOpen,
  onDelete,
}: {
  p: ProjectSummary;
  onOpen: () => void;
  onDelete?: () => void;
}) {
  const { t } = useI18n();
  const ratio = p.progress / 100;
  const hue = completionColor(ratio);
  const counts: HealthCounts = {
    running: p.agents_active,
    blocked: p.agents_blocked,
    done: Math.max(0, p.agents_total - p.agents_active - p.agents_blocked),
    waiting: 0,
  };
  return (
    <button className="pcard" style={{ "--hue": hue } as CSSProperties} onClick={onOpen}>
      <div className="pcard-top">
        <div className="pj-glyph">{monogram(p.name)}</div>
        <div className="pcard-id">
          <div className="nm">{p.name}</div>
          <div className="ds">{p.description ?? p.status}</div>
        </div>
        {p.agents_active > 0 && (
          <span className="equalizer live" style={{ "--clr": "var(--run)" } as CSSProperties}>
            {[0, 1, 2, 3, 4].map((i) => (<span className="eq-bar" key={i} />))}
          </span>
        )}
        <PjRing ratio={ratio} pct={p.progress} size={50} />
      </div>
      <div className="pcard-metrics">
        <span className="pjm"><b className="num">{p.agents_total}</b> {t("u_agents")}</span>
        <span className="pjm"><b className="num">{p.tasks_done}/{p.tasks_total}</b> {t("u_tasks")}</span>
        <span className="pjm"><span className="badge st-mini">{p.status}</span></span>
      </div>
      <HealthBar counts={counts} />
      <div className="pcard-foot">
        {p.agents_blocked > 0 && <span className="pcard-flag block">{Icon.alert({})}{p.agents_blocked} {t("to_review")}</span>}
        {onDelete ? (
          <span
            role="button"
            className="pcard-del"
            onClick={(e) => { e.stopPropagation(); if (confirm(`Supprimer « ${p.name} » ?`)) onDelete(); }}
          >
            {Icon.trash({ style: { width: 14, height: 14 } })}
          </span>
        ) : null}
        <span className="pcard-go">{t("open")} {Icon.chevron({})}</span>
      </div>
    </button>
  );
}

/* ---- accordéon agent ---- */
function AgentTile({
  agent,
  subtasks,
  expanded,
  onToggle,
}: {
  agent: Agent;
  subtasks: { title: string; progress: number; state: string }[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  const s = statusOf(agent.state);
  const total = agent.tasks_total ?? subtasks.length;
  const done = agent.tasks_done ?? subtasks.filter((t) => t.state === "done").length;
  const pct = agent.state === "done" ? 100 : agent.progress;
  return (
    <div className={"atile " + (expanded ? "open" : "")}>
      <div className="atile-head" onClick={onToggle}>
        <span className="atile-bot" style={{ color: s.clr }}>
          <Ant state={antStateOf(agent.state)} color={s.clr} size={26} />
        </span>
        <span className="atile-name">{agent.label ?? agent.agent}</span>
        <Badge state={agent.state} />
        <span className="atile-mini">
          <span className="bar"><i style={{ width: pct + "%", background: s.clr }} /></span>
          {total > 0 && <span className="num">{done}/{total}</span>}
        </span>
        <span className={"atile-chev" + (expanded ? " up" : "")}>{Icon.chevron({})}</span>
      </div>
      {expanded && (
        <div className="atile-detail" style={{ animation: "none", opacity: 1 }}>
          <div className="atile-task">{agent.state === "blocked" && agent.blocker ? `⛔ ${agent.blocker}` : agent.task ?? "—"}</div>
          {subtasks.length > 0 ? (
            <div className="atile-tasks">
              {subtasks.slice(0, 6).map((st, i) => {
                const stt = st.state === "done" ? "done" : st.state === "working" ? "active" : "todo";
                return (
                  <div className={"atask " + stt} key={i}>
                    <span className="ic">
                      {stt === "done" ? Icon.check({}) : stt === "active" ? <span className="spin" /> : <span className="ring" />}
                    </span>
                    <span className="lbl">{st.title}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="atile-tasks empty">{t("no_plan")}</div>
          )}
          <div className="atile-actions">
            <span className="am">{Icon.clock({})}<b>{fmtAge(agent.age_seconds)}</b></span>
            {agent.module && <span className="am">{Icon.layers({})}<b>{agent.module}</b></span>}
            {agent.branch && <span className="am num">{Icon.pr({})}<b>{agent.branch}</b></span>}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- barre de résumé (atlas) ---- */
export function ProjectsSummary({ projects }: { projects: ProjectSummary[] }) {
  const { t } = useI18n();
  const running = projects.reduce((s, p) => s + p.agents_active, 0);
  const blocked = projects.reduce((s, p) => s + p.agents_blocked, 0);
  const doneTasks = projects.reduce((s, p) => s + p.tasks_done, 0);
  const totalTasks = projects.reduce((s, p) => s + p.tasks_total, 0);
  const globalPct = totalTasks ? Math.round((doneTasks / totalTasks) * 100) : 0;
  return (
    <div className="pj-summary">
      <div className="pjs"><div className="pjs-v num">{projects.length}</div><div className="pjs-k">{Icon.folder({})} {t("sum_projects")}</div></div>
      <div className="pjs-div" />
      <div className="pjs"><div className="pjs-v num" style={{ color: "var(--run)" }}>{running}</div><div className="pjs-k">{Icon.pulse({})} {t("sum_active")}</div></div>
      <div className="pjs"><div className="pjs-v num" style={{ color: blocked ? "var(--block)" : "var(--tx-hi)" }}>{blocked}</div><div className="pjs-k">{Icon.alert({})} {t("sum_review")}</div></div>
      <div className="pjs"><div className="pjs-v num">{doneTasks}<small>/{totalTasks}</small></div><div className="pjs-k">{Icon.check({})} {t("sum_tasks")}</div></div>
      <div className="pjs-grow" />
      <div className="pj-progmega">
        <div className="lbl">{t("global_progress")}</div>
        <div className="bar"><i style={{ width: globalPct + "%" }} /></div>
        <div className="pct num">{globalPct}%</div>
      </div>
    </div>
  );
}

/* ---- panneau Git (GitHub) ---- */
function GitPanel({ projectId, repo }: { projectId: string; repo: string | null }) {
  const { t } = useI18n();
  const [git, setGit] = useState<GitInfo | null>(null);
  useEffect(() => {
    if (!repo) { setGit(null); return; }
    let alive = true;
    getProjectGit(projectId).then((g) => { if (alive) setGit(g); }).catch(() => {});
    return () => { alive = false; };
  }, [projectId, repo]);

  if (!repo) return null;
  return (
    <div className="git-panel">
      <div className="git-head">
        {Icon.pr({ style: { width: 16, height: 16 } })}
        <span className="git-repo">{git?.url ? <a href={git.url} target="_blank" rel="noreferrer">{repo}</a> : repo}</span>
        {git?.available && (
          <>
            <span className="git-chip">{git.default_branch}</span>
            <span className="git-chip">{git.branch_count} {t("git_branches_n")}</span>
            <span className="git-chip">★ {git.stars}</span>
            <span className="git-chip">{git.open_issues} {t("git_issues")}</span>
          </>
        )}
      </div>
      {git && !git.available && <div className="git-empty">{t("git_unavail")}{git.error ? ` (${git.error})` : ""}</div>}
      {git?.available && (
        <div className="git-cols">
          <div>
            <div className="git-sub">{t("git_commits")}</div>
            {(git.commits ?? []).map((c) => (
              <div className="git-commit" key={c.sha}><span className="sha">{c.sha}</span><span className="msg">{c.message}</span></div>
            ))}
          </div>
          <div>
            <div className="git-sub">{t("git_prs")} ({git.prs?.length ?? 0})</div>
            {(git.prs ?? []).length === 0 && <div className="git-empty">—</div>}
            {(git.prs ?? []).slice(0, 8).map((p) => (
              <div className="git-pr" key={p.number}><span className="n">#{p.number}</span><span className="ti">{p.title}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- détail projet ---- */
export function ProjectDetailPanel({
  project,
  onBack,
  onDelete,
  onStatus,
  onRepo,
  canEdit,
}: {
  project: ProjectDetail;
  onBack: () => void;
  onDelete?: () => void;
  onStatus?: (status: string) => void;
  onRepo?: (repo: string) => void;
  canEdit?: boolean;
}) {
  const { t } = useI18n();
  const [openId, setOpenId] = useState<string | null>(null);
  const ratio = project.progress / 100;
  const hue = completionColor(ratio);
  const counts = healthFrom(project.agents);

  // subtasks par agent (via les tâches du projet)
  const subtasksOf = (key: string) => {
    const task: Task | undefined = project.tasks.find((tk) => tk.agents.some((a) => a.agent === key));
    return task ? task.subtasks : [];
  };

  const stats = [
    { k: t("st_active"), v: counts.running, clr: "var(--run)", ic: Icon.pulse },
    { k: t("sum_review"), v: counts.blocked, clr: counts.blocked ? "var(--block)" : "var(--tx-hi)", ic: Icon.alert },
    { k: t("st_done"), v: counts.done, clr: "var(--done)", ic: Icon.check },
    { k: t("sum_tasks"), v: `${project.tasks_done}/${project.tasks_total}`, ic: Icon.layers },
  ];

  return (
    <div className="pj-page pd" style={{ "--hue": hue } as CSSProperties}>
      <button className="pd-back" onClick={onBack}>{Icon.back({})} {t("nav_projects")}</button>

      <header className="pd-head">
        <div className="pj-glyph big">{monogram(project.name)}</div>
        <div className="pd-id">
          <div className="nm">{project.name}</div>
          <div className="ds">{project.description ?? project.status}</div>
          <div className="pd-tags">
            <span className="pd-tag"><b className="num">{project.agents_total}</b> {t("u_agents")}</span>
            <span className="pd-tag"><b className="num">{project.tasks_done}/{project.tasks_total}</b> {t("u_tasks")}</span>
            <span className="pd-tag">{project.status}</span>
          </div>
        </div>
        {project.agents_active > 0 && (
          <span className="equalizer live" style={{ "--clr": "var(--run)" } as CSSProperties}>
            {[0, 1, 2, 3, 4].map((i) => (<span className="eq-bar" key={i} />))}
          </span>
        )}
        <PjRing ratio={ratio} pct={project.progress} size={84} sw={6} />
      </header>

      {canEdit && (onStatus || onDelete) && (
        <div className="pd-editbar">
          {onStatus && (
            <>
              <span>{t("status_lbl")}</span>
              <select value={project.status} onChange={(e) => onStatus(e.target.value)} className="pd-select">
                {["proposed", "validated", "in_dev", "done", "archived"].map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </>
          )}
          {onRepo && (
            <input
              className="pd-select"
              style={{ minWidth: 180 }}
              defaultValue={project.repo ?? ""}
              placeholder={t("git_repo")}
              onBlur={(e) => { if (e.target.value !== (project.repo ?? "")) onRepo(e.target.value); }}
            />
          )}
          {onDelete && (
            <button className="pd-del" onClick={() => { if (confirm(`Supprimer « ${project.name} » ?`)) onDelete(); }}>
              {Icon.trash({ style: { width: 14, height: 14 } })} {t("del")}
            </button>
          )}
        </div>
      )}

      <div className="pd-healthrow"><HealthBar counts={counts} /></div>

      <div className="pd-stats">
        {stats.map((s, i) => (
          <div className="pd-stat" key={i}>
            <div className="pd-stat-k">{s.ic({})} {s.k}</div>
            <div className="pd-stat-v num" style={{ color: s.clr ?? "var(--tx-hi)" }}>{s.v}</div>
          </div>
        ))}
      </div>

      {project.repo && (
        <>
          <div className="section-head"><h2>{t("git_section")}</h2></div>
          <GitPanel projectId={project.id} repo={project.repo} />
        </>
      )}

      <div className="section-head"><h2>{t("agents_sec")}</h2><span className="hint">{project.agents.length} · {counts.running} {t("hint_active")}</span></div>
      <div className="pj-body">
        {project.agents.length === 0 && <div className="pd-empty">{t("no_agent")}</div>}
        {project.agents.map((a) => (
          <AgentTile
            key={a.agent}
            agent={a}
            subtasks={subtasksOf(a.agent)}
            expanded={openId === a.agent}
            onToggle={() => setOpenId((cur) => (cur === a.agent ? null : a.agent))}
          />
        ))}
      </div>
    </div>
  );
}
