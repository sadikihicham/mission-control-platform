"use client";
// @ts-nocheck
import { AGENTS, STATUS, fmtCost } from "@/lib/mc-data";
import { Icon } from "@/components/mc/icons";
import { Ant, antStateOf } from "@/components/mc/Ant";
import { useI18n } from "@/lib/i18n";

const HORD = ["blocked", "running", "waiting", "done"];

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
  },
};

function hueFor(p) {
  const t = Math.max(0, Math.min(1, p));
  return `hsl(${(4 + 138 * t).toFixed(0)} 64% 52%)`;
}

export function Home({ onOpen = () => {}, onReview = () => {}, onOpenProject = () => {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const agents = AGENTS;

  const counts = { running: 0, waiting: 0, blocked: 0, done: 0 };
  agents.forEach((a) => {
    counts[a.status] = (counts[a.status] || 0) + 1;
  });
  const totalTasks = agents.reduce((s, a) => s + (a.steps || []).length, 0);
  const doneTasks = agents.reduce(
    (s, a) => s + (a.steps || []).filter((t) => t.done).length,
    0
  );
  const globalPct = totalTasks ? Math.round((doneTasks / totalTasks) * 100) : 0;
  const blocked = agents.filter((a) => a.status === "blocked");
  const totalCost = agents.reduce((s, a) => s + (a.cost || 0), 0);

  // projects by completion (most at risk first)
  const groups = {};
  agents.forEach((a) => {
    (groups[a.repo] = groups[a.repo] || []).push(a);
  });
  const projects = Object.entries(groups)
    .map(([repo, items]) => {
      const td = items.reduce(
        (s, a) => s + (a.steps || []).filter((t) => t.done).length,
        0
      );
      const tt = items.reduce((s, a) => s + (a.steps || []).length, 0);
      const bl = items.filter((a) => a.status === "blocked").length;
      return { repo, items, pct: tt ? Math.round((td / tt) * 100) : 0, bl };
    })
    .sort((a, b) => b.bl - a.bl || a.pct - b.pct)
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
          <div className="hk">
            <div className="hk-v num">{fmtCost(totalCost)}</div>
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
          {HORD.map((k) =>
            counts[k] ? (
              <i
                key={k}
                style={{ flex: counts[k], background: STATUS[k].clr }}
                title={counts[k] + " " + t(k)}
              ></i>
            ) : null
          )}
        </div>
        <div className="hh-legend">
          {HORD.map((k) =>
            counts[k] ? (
              <span key={k}>
                <span className="d" style={{ background: STATUS[k].clr }}></span>
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
              <button className="hrow" key={a.id} onClick={() => onReview(a)}>
                <span className="hrow-ic" style={{ color: STATUS.blocked.clr }}>
                  <Ant state="searching" color={STATUS.blocked.clr} size={26} />
                </span>
                <span className="hrow-txt">
                  <span className="hrow-n">{a.name}</span>
                  <span className="hrow-s">
                    {a.pendingAction ? a.pendingAction.title : a.repo}
                  </span>
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
            {projects.map((p) => (
              <button
                className="hrow"
                key={p.repo}
                onClick={() => onOpenProject(p.repo)}
              >
                <span
                  className="hrow-ring"
                  style={{ "--hue": hueFor(p.pct / 100) }}
                >
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
                      strokeDashoffset={2 * Math.PI * 13 * (1 - p.pct / 100)}
                      transform="rotate(-90 17 17)"
                    />
                  </svg>
                  <b className="num" style={{ color: "var(--hue)" }}>
                    {p.pct}
                  </b>
                </span>
                <span className="hrow-txt">
                  <span className="hrow-n">{p.repo}</span>
                  <span className="hrow-s">
                    {p.items.length} {p.items.length > 1 ? t("agents") : t("agent")}
                    {p.bl ? " · " + p.bl + " " + t("n_to_review") : ""}
                  </span>
                </span>
                {p.bl > 0 && <span className="hrow-flag">{Icon.alert({})}</span>}
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
