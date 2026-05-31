"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { getAgentActivity, type Activity, type Agent } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { useI18n } from "@/lib/i18n";
import { completionColor, fmtAge, statusOf } from "@/lib/mc";
import { Badge, PjRing } from "@/components/mc/Projects";
import { Ant, antStateOf } from "@/components/mc/Ant";

type SubTask = { title: string; progress: number; state: string };

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" });
}

export function AgentDetail({
  agent,
  subtasks,
  onBack,
}: {
  agent: Agent;
  subtasks: SubTask[];
  onBack: () => void;
}) {
  const { t } = useI18n();
  const [tab, setTab] = useState<"activity" | "progress">("activity");
  const [acts, setActs] = useState<Activity[]>([]);
  const s = statusOf(agent.state);
  const pct = agent.state === "done" ? 100 : agent.progress;

  useEffect(() => {
    let alive = true;
    const tick = async () => { try { const a = await getAgentActivity(agent.agent); if (alive) setActs(a); } catch { /* */ } };
    tick();
    const id = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(id); };
  }, [agent.agent]);

  const vitals = [
    { k: t("v_progress"), v: pct + "%", clr: s.clr },
    { k: t("v_tasks"), v: agent.tasks_total ? `${agent.tasks_done ?? 0}/${agent.tasks_total}` : "—" },
    { k: t("v_beat"), v: fmtAge(agent.age_seconds) },
    { k: t("v_state"), v: s.label, clr: s.clr },
  ];

  return (
    <div className="pj-page pd" style={{ "--hue": completionColor(pct / 100) } as CSSProperties}>
      <button className="pd-back" onClick={onBack}>{Icon.back({})} {t("nav_overview")}</button>

      <header className="pd-head" style={{ "--hue": s.clr } as CSSProperties}>
        <div className="pj-glyph big" style={{ background: `color-mix(in oklab, ${s.clr} 18%, var(--bg-3))`, color: s.clr }}>
          <Ant state={antStateOf(agent.state)} color={s.clr} size={48} />
        </div>
        <div className="pd-id">
          <div className="nm">{agent.label ?? agent.agent}</div>
          <div className="ds">{agent.state === "blocked" && agent.blocker ? `⛔ ${agent.blocker}` : agent.task ?? "—"}</div>
          <div className="pd-tags">
            <Badge state={agent.state} />
            {agent.module && <span className="pd-tag">{Icon.layers({})} {agent.module}</span>}
            {agent.branch && <span className="pd-tag">{Icon.pr({})} {agent.branch}</span>}
          </div>
        </div>
        <PjRing ratio={pct / 100} pct={pct} size={84} sw={6} />
      </header>

      <div className="pd-stats">
        {vitals.map((v, i) => (
          <div className="pd-stat" key={i}>
            <div className="pd-stat-k">{v.k}</div>
            <div className="pd-stat-v num" style={{ color: v.clr ?? "var(--tx-hi)" }}>{v.v}</div>
          </div>
        ))}
      </div>

      <div className="tabs" style={{ marginTop: 4 }}>
        <button className={"tab" + (tab === "activity" ? " active" : "")} onClick={() => setTab("activity")}>{Icon.terminal({})} {t("d_activity")}</button>
        <button className={"tab" + (tab === "progress" ? " active" : "")} onClick={() => setTab("progress")}>{Icon.check({})} {t("d_progress")}</button>
      </div>

      {tab === "activity" ? (
        <div className="term" style={{ maxHeight: 420, overflowY: "auto", borderRadius: "var(--r-md)", border: "1px solid var(--border-soft)", padding: 12 }}>
          {acts.length === 0 && <div style={{ color: "var(--tx-lo)", fontSize: 13 }}>{t("d_noact")}</div>}
          {acts.map((a, i) => {
            const as = statusOf(a.state ?? "idle");
            return (
              <div key={i} className="mono" style={{ display: "flex", gap: 10, alignItems: "baseline", padding: "3px 0", fontSize: 12.5 }}>
                <span style={{ color: "var(--tx-dim)", flex: "none" }}>{fmtTime(a.created_at)}</span>
                <span style={{ color: as.clr, flex: "none", textTransform: "uppercase", fontSize: 10.5, fontWeight: 600 }}>{a.state ?? a.type}</span>
                <span style={{ color: "var(--tx-mid)" }}>{a.task ?? a.type}{a.progress != null ? `  ·  ${a.progress}%` : ""}</span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="pj-body">
          {subtasks.length === 0 && <div className="pd-empty">{t("no_plan")}</div>}
          {subtasks.length > 0 && (
            <div className="atile-tasks" style={{ background: "var(--bg-2)", border: "1px solid var(--border-soft)", borderRadius: "var(--r-md)", padding: 14 }}>
              {subtasks.map((st, i) => {
                const stt = st.state === "done" ? "done" : st.state === "working" ? "active" : "todo";
                return (
                  <div className={"atask " + stt} key={i}>
                    <span className="ic">{stt === "done" ? Icon.check({}) : stt === "active" ? <span className="spin" /> : <span className="ring" />}</span>
                    <span className="lbl">{st.title}</span>
                    <span className="num" style={{ marginInlineStart: "auto", color: "var(--tx-lo)", fontSize: 12 }}>{st.progress}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
