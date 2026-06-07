// @ts-nocheck
"use client";
import { useEffect, useState } from "react";
import {
  getAgents,
  getProjects,
  type Agent,
  type ProjectSummary,
} from "@/lib/api";
import {
  statusOf,
  healthFrom,
  HEALTH_META,
  HEALTH_ORDER,
  bucketOf,
  completionColor,
} from "@/lib/mc";
import { Icon } from "@/components/mc/icons";
import { Ant } from "@/components/mc/Ant";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    mission_control: "Mission Control",
    glance: "Opération en un coup d'œil",
    running_agents: "Agents en cours",
    to_review: "À valider",
    cost_today: "Coût du jour",
    overall_progress: "Avancement global",
    fleet_health: "Santé de la flotte",
    blocked: "bloqués",
    running: "en cours",
    waiting: "en attente",
    done: "terminés",
    next_approvals: "Prochaines validations",
    at_risk_projects: "Projets à risque",
    see_all: "Tout voir",
    nothing_waiting: "Rien n'attend votre attention",
    examine: "Examiner",
    agents: "agents",
    agent: "agent",
    n_to_review: "à valider",
    cost_na: "Non suivi côté serveur",
    no_agents: "Aucun agent actif",
    no_projects: "Aucun projet",
  },
  en: {
    mission_control: "Mission Control",
    glance: "Operation at a glance",
    running_agents: "Running agents",
    to_review: "To review",
    cost_today: "Cost today",
    overall_progress: "Overall progress",
    fleet_health: "Fleet health",
    blocked: "blocked",
    running: "running",
    waiting: "queued",
    done: "done",
    next_approvals: "Next approvals",
    at_risk_projects: "At-risk projects",
    see_all: "See all",
    nothing_waiting: "Nothing waiting on you",
    examine: "Examine",
    agents: "agents",
    agent: "agent",
    n_to_review: "to review",
    cost_na: "Non suivi côté serveur",
    no_agents: "Aucun agent actif",
    no_projects: "Aucun projet",
  },
  ar: {
    mission_control: "مركز التحكم",
    glance: "نظرة عامة على العمليات",
    running_agents: "الوكلاء النشطون",
    to_review: "للمراجعة",
    cost_today: "تكلفة اليوم",
    overall_progress: "التقدم الإجمالي",
    fleet_health: "حالة الأسطول",
    blocked: "محظور",
    running: "قيد التشغيل",
    waiting: "في الانتظار",
    done: "منجز",
    next_approvals: "الموافقات التالية",
    at_risk_projects: "المشاريع المعرّضة للخطر",
    see_all: "عرض الكل",
    nothing_waiting: "لا شيء بانتظارك",
    examine: "فحص",
    agents: "وكلاء",
    agent: "وكيل",
    n_to_review: "للمراجعة",
    cost_na: "Non suivi côté serveur",
    no_agents: "Aucun agent actif",
    no_projects: "Aucun projet",
  },
};

function hueFor(p) {
  return completionColor(Math.max(0, Math.min(1, p)));
}

export function Home({ onOpen = () => {}, onReview = () => {}, onOpenProject = () => {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);

  // Self-fetch des données live.
  const [agents, setAgents] = useState<Agent[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  useEffect(() => {
    let on = true;
    getAgents()
      .then((a) => on && setAgents(a))
      .catch(() => {});
    getProjects()
      .then((p) => on && setProjects(p))
      .catch(() => {});
    return () => {
      on = false;
    };
  }, []);

  // Compteurs de santé dérivés des états live.
  const counts = healthFrom(agents);
  // Avancement global = moyenne des progress live des agents (0-100).
  const globalPct = agents.length
    ? Math.round(agents.reduce((s, a) => s + (a.progress || 0), 0) / agents.length)
    : 0;
  // Agents à valider = bloqués/en erreur.
  const blocked = agents.filter((a) => bucketOf(a.state) === "blocked");

  // Projets à risque : bloqués d'abord, puis avancement le plus faible.
  const riskProjects = [...projects]
    .sort((a, b) => (b.agents_blocked || 0) - (a.agents_blocked || 0) || a.progress - b.progress)
    .slice(0, 4);

  return (
    <div className="home">
      <div className="home-hero">
        <div className="hh-text">
          <div className="hh-eyebrow">{Icon.spark({})} {t("mission_control")}</div>
          <h1>{t("glance")}</h1>
        </div>
        <div className="hh-kpis">
          <button className="hk" onClick={onOpen}>
            <div className="hk-v num" style={{ color: "var(--run)" }}>
              {counts.running}
            </div>
            <div className="hk-k">
              {Icon.pulse({})} {t("running_agents")}
            </div>
          </button>
          <button className="hk" onClick={onReview}>
            <div
              className="hk-v num"
              style={{ color: counts.blocked ? "var(--block)" : "var(--tx-hi)" }}
            >
              {counts.blocked}
            </div>
            <div className="hk-k">
              {Icon.alert({})} {t("to_review")}
            </div>
          </button>
          {/* Coût non suivi côté serveur — dégradé en "—". */}
          <div className="hk" title={t("cost_na")}>
            <div className="hk-v num">—</div>
            <div className="hk-k">
              {Icon.coin({})} {t("cost_today")}
            </div>
          </div>
          <div className="hk hk-prog">
            <div className="hk-v num">
              {globalPct}
              <small>%</small>
            </div>
            <div className="hk-k">
              {Icon.check({})} {t("overall_progress")}
            </div>
            <div className="hk-bar">
              <i style={{ width: globalPct + "%" }}></i>
            </div>
          </div>
        </div>
      </div>

      <div className="home-health">
        <div className="hh-label">{t("fleet_health")}</div>
        <div className="hh-bar">
          {HEALTH_ORDER.map((k) =>
            counts[k] ? (
              <i
                key={k}
                style={{ flex: counts[k], background: HEALTH_META[k].clr }}
                title={counts[k] + " " + t(k)}
              ></i>
            ) : null
          )}
        </div>
        <div className="hh-legend">
          {HEALTH_ORDER.map((k) =>
            counts[k] ? (
              <span key={k}>
                <span className="d" style={{ background: HEALTH_META[k].clr }}></span>
                {counts[k]} {t(k)}
              </span>
            ) : null
          )}
        </div>
      </div>

      <div className="home-grid">
        <section className="hcard hcard-pending">
          <div className="hc-head">
            <h2>{Icon.alert({})} {t("next_approvals")}</h2>
            {blocked.length > 0 && (
              <button className="hc-all" onClick={onReview}>
                {t("see_all")}
              </button>
            )}
          </div>
          <div className="hc-body">
            {blocked.length === 0 && (
              <div className="hc-empty">
                {Icon.check({})}
                <span>{t("nothing_waiting")}</span>
              </div>
            )}
            {blocked.map((a) => (
              <button className="hrow" key={a.agent} onClick={() => onReview(a)}>
                <span className="hrow-ic" style={{ color: statusOf(a.state).clr }}>
                  <Ant state="searching" color={statusOf(a.state).clr} size={26} />
                </span>
                <span className="hrow-txt">
                  <span className="hrow-n">{a.label || a.agent}</span>
                  <span className="hrow-s">{a.blocker || a.task || a.module || "—"}</span>
                </span>
                <span className="hrow-cta">
                  {t("examine")} {Icon.chevron({})}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="hcard">
          <div className="hc-head">
            <h2>{Icon.folder({})} {t("at_risk_projects")}</h2>
            <button className="hc-all" onClick={onOpenProject}>
              {t("see_all")}
            </button>
          </div>
          <div className="hc-body">
            {riskProjects.length === 0 && (
              <div className="hc-empty">
                {Icon.folder({})}
                <span>{t("no_projects")}</span>
              </div>
            )}
            {riskProjects.map((p) => {
              const pct = Math.round(p.progress || 0);
              const bl = p.agents_blocked || 0;
              const nb = p.agents_total || 0;
              return (
                <button className="hrow" key={p.id} onClick={() => onOpenProject(p.id)}>
                  <span className="hrow-ring" style={{ "--hue": hueFor(pct / 100) }}>
                    <svg width="34" height="34" viewBox="0 0 34 34">
                      <circle
                        cx="17"
                        cy="17"
                        r="13"
                        fill="none"
                        stroke="var(--bg-3)"
                        strokeWidth="3.5"
                      />
                      <circle
                        cx="17"
                        cy="17"
                        r="13"
                        fill="none"
                        stroke="var(--hue)"
                        strokeWidth="3.5"
                        strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 13}
                        strokeDashoffset={2 * Math.PI * 13 * (1 - pct / 100)}
                        transform="rotate(-90 17 17)"
                      />
                    </svg>
                    <b className="num" style={{ color: "var(--hue)" }}>
                      {pct}
                    </b>
                  </span>
                  <span className="hrow-txt">
                    <span className="hrow-n">{p.name}</span>
                    <span className="hrow-s">
                      {nb} {nb > 1 ? t("agents") : t("agent")}
                      {bl ? " · " + bl + " " + t("n_to_review") : ""}
                    </span>
                  </span>
                  {bl > 0 && <span className="hrow-flag">{Icon.alert({})}</span>}
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
