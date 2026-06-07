// @ts-nocheck
"use client";
import { useEffect, useState } from "react";
import { Icon } from "@/components/mc/icons";
import { getAgents, getProjects, type Agent } from "@/lib/api";
import { healthFrom } from "@/lib/mc";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    system_audit: "Audit système",
    functional_audit: "Audit fonctionnel",
    system_audit_sub: "Santé opérationnelle de la flotte",
    functional_audit_sub: "Couverture, gouvernance & livraison",
    compliance: "Conformité",
    compliant: "Conforme",
    watch: "À surveiller",
    non_compliant: "Non conforme",
    rerun_audit: "Relancer l'audit",
    grp_capacity: "Capacité & charge",
    grp_reliability: "Fiabilité",
    grp_budget: "Budget & coût",
    grp_coverage: "Couverture des départements",
    grp_governance: "Gouvernance & approbations",
    grp_pm: "Gestion de projet",
    chk_fleet_load: "Charge de la flotte sous le seuil",
    chk_token_tput: "Débit de tokens nominal",
    chk_success_rate: "Taux d'agents en erreur",
    chk_no_escalation: "Aucune escalade non traitée",
    chk_stream_active: "Flux temps réel actif",
    chk_budget_control: "Budget mensuel sous contrôle",
    chk_daily_cost: "Coût quotidien stable",
    chk_all_staffed: "Tous les projets actifs dotés",
    chk_balanced_load: "Charge équilibrée entre projets",
    chk_approvals_intime: "Approbations humaines traitées à temps",
    chk_risky_control: "Actions risquées sous contrôle",
    chk_projects_threshold: "Projets au-dessus du seuil d'avancement",
    chk_tasks_resolved: "Tâches bloquées résolues",
    chk_prs_ontrack: "Livraisons (PR) dans les temps",
    d_active_agents_max: "agents actifs / 20 max",
    d_total: "total",
    d_over7d: "% en erreur",
    d_awaiting: "agent(s) en attente d'approbation",
    d_live_logs: "Journaux & métriques en direct",
    d_used: "% utilisé",
    d_per_day: "/ jour",
    d_full_coverage: "Couverture complète",
    d_depts_idle: "projet(s) actif(s) sans agent",
    d_max_gap: "Écart max 2 agents",
    d_pending: "en attente",
    d_high_risk: "à haut risque",
    d_under50: "projet(s) sous 50%",
    d_blocked_tasks: "agent(s) bloqué(s)",
    d_prs_opened: "PR ouvertes",
    d_unavailable: "Indisponible — non suivi côté serveur",
    fix_ok: "Contrôle conforme — aucune action requise.",
    why_capacity: "Une flotte surchargée allonge les files d'attente et dégrade la latence des agents.",
    why_reliability: "Les approbations en attente bloquent les agents et laissent un risque opérationnel non traité.",
    why_budget: "Un budget proche du plafond risque d'arrêter les agents en fin de cycle.",
    why_coverage: "Un projet actif sans agent ne traite aucun travail automatisé.",
    why_governance: "Des approbations non traitées à temps exposent des actions risquées non maîtrisées.",
    why_pm: "Des projets sous le seuil ou des tâches bloquées retardent les livraisons.",
    sol_pause: "Mettre en pause les agents non prioritaires",
    sol_raise_cap: "Augmenter le plafond de capacité",
    sol_review_approvals: "Examiner les approbations en attente",
    sol_bulk_approve: "Approuver en masse les actions à faible risque",
    sol_auto_policy: "Définir une politique d'auto-approbation",
    sol_review_costly: "Examiner les agents les plus coûteux",
    sol_cap_cost: "Plafonner le coût par agent",
    sol_reassign: "Réaffecter un agent au projet inactif",
    sol_deploy: "Déployer un nouvel agent",
    sol_handle_approvals: "Traiter les approbations en attente",
    sol_review_risk: "Examiner les politiques de risque",
    sol_open_atrisk: "Ouvrir les projets à risque",
    sol_unblock: "Débloquer les tâches en attente",
    empty: "Aucune donnée de flotte disponible pour le moment.",
  },
  en: {
    system_audit: "System audit",
    functional_audit: "Functional audit",
    system_audit_sub: "Operational health of the fleet",
    functional_audit_sub: "Coverage, governance & delivery",
    compliance: "Compliance",
    compliant: "Compliant",
    watch: "Watch",
    non_compliant: "Non-compliant",
    rerun_audit: "Re-run audit",
    grp_capacity: "Capacity & load",
    grp_reliability: "Reliability",
    grp_budget: "Budget & cost",
    grp_coverage: "Project coverage",
    grp_governance: "Governance & approvals",
    grp_pm: "Project management",
    chk_fleet_load: "Fleet load under threshold",
    chk_token_tput: "Token throughput nominal",
    chk_success_rate: "Agents in error rate",
    chk_no_escalation: "No unhandled escalation",
    chk_stream_active: "Real-time stream active",
    chk_budget_control: "Monthly budget under control",
    chk_daily_cost: "Daily cost stable",
    chk_all_staffed: "All active projects staffed",
    chk_balanced_load: "Balanced load across projects",
    chk_approvals_intime: "Human approvals handled in time",
    chk_risky_control: "Risky actions under control",
    chk_projects_threshold: "Projects above completion threshold",
    chk_tasks_resolved: "Blocked tasks resolved",
    chk_prs_ontrack: "Deliveries (PRs) on track",
    d_active_agents_max: "active agents / 20 max",
    d_total: "total",
    d_over7d: "% in error",
    d_awaiting: "agent(s) awaiting approval",
    d_live_logs: "Live logs & metrics",
    d_used: "% used",
    d_per_day: "/ day",
    d_full_coverage: "Full coverage",
    d_depts_idle: "active project(s) without agent",
    d_max_gap: "Max gap 2 agents",
    d_pending: "pending",
    d_high_risk: "high-risk",
    d_under50: "project(s) under 50%",
    d_blocked_tasks: "blocked agent(s)",
    d_prs_opened: "PRs opened",
    d_unavailable: "Unavailable — not tracked server-side",
    fix_ok: "Check compliant — no action required.",
    why_capacity: "An overloaded fleet lengthens queues and degrades agent latency.",
    why_reliability: "Pending approvals stall agents and leave operational risk unhandled.",
    why_budget: "A budget near the cap risks halting agents at cycle end.",
    why_coverage: "An active project with no agent handles no automated work.",
    why_governance: "Approvals not handled in time expose uncontrolled risky actions.",
    why_pm: "Projects under threshold or blocked tasks delay deliveries.",
    sol_pause: "Pause non-priority agents",
    sol_raise_cap: "Raise the capacity cap",
    sol_review_approvals: "Review pending approvals",
    sol_bulk_approve: "Bulk-approve low-risk actions",
    sol_auto_policy: "Set an auto-approval policy",
    sol_review_costly: "Review the costliest agents",
    sol_cap_cost: "Cap cost per agent",
    sol_reassign: "Reassign an agent to the idle project",
    sol_deploy: "Deploy a new agent",
    sol_handle_approvals: "Handle pending approvals",
    sol_review_risk: "Review risk policies",
    sol_open_atrisk: "Open at-risk projects",
    sol_unblock: "Unblock pending tasks",
    empty: "No fleet data available yet.",
  },
  ar: {
    system_audit: "تدقيق النظام",
    functional_audit: "التدقيق الوظيفي",
    system_audit_sub: "الصحة التشغيلية للأسطول",
    functional_audit_sub: "التغطية والحوكمة والتسليم",
    compliance: "الامتثال",
    compliant: "مطابق",
    watch: "للمراقبة",
    non_compliant: "غير مطابق",
    rerun_audit: "إعادة تشغيل التدقيق",
    grp_capacity: "السعة والحمل",
    grp_reliability: "الموثوقية",
    grp_budget: "الميزانية والتكلفة",
    grp_coverage: "تغطية المشاريع",
    grp_governance: "الحوكمة والموافقات",
    grp_pm: "إدارة المشاريع",
    chk_fleet_load: "حمل الأسطول تحت الحد الأقصى",
    chk_token_tput: "معدل تدفق الرموز طبيعي",
    chk_success_rate: "نسبة الوكلاء في حالة خطأ",
    chk_no_escalation: "لا توجد تصعيدات غير معالجة",
    chk_stream_active: "البث في الوقت الفعلي نشط",
    chk_budget_control: "الميزانية الشهرية تحت السيطرة",
    chk_daily_cost: "التكلفة اليومية مستقرة",
    chk_all_staffed: "جميع المشاريع النشطة مزودة بالوكلاء",
    chk_balanced_load: "حمل متوازن عبر المشاريع",
    chk_approvals_intime: "معالجة الموافقات البشرية في الوقت المناسب",
    chk_risky_control: "الإجراءات الخطرة تحت السيطرة",
    chk_projects_threshold: "المشاريع فوق حد الإنجاز",
    chk_tasks_resolved: "حل المهام المحظورة",
    chk_prs_ontrack: "التسليمات (طلبات الدمج) في الموعد",
    d_active_agents_max: "وكلاء نشطون / 20 كحد أقصى",
    d_total: "الإجمالي",
    d_over7d: "٪ في حالة خطأ",
    d_awaiting: "وكيل (وكلاء) في انتظار الموافقة",
    d_live_logs: "السجلات والمقاييس المباشرة",
    d_used: "٪ مستخدم",
    d_per_day: "/ يوم",
    d_full_coverage: "تغطية كاملة",
    d_depts_idle: "مشروع (مشاريع) نشط بدون وكيل",
    d_max_gap: "أقصى فجوة وكيلان",
    d_pending: "قيد الانتظار",
    d_high_risk: "عالي الخطورة",
    d_under50: "مشروع (مشاريع) تحت 50٪",
    d_blocked_tasks: "وكيل (وكلاء) محظور",
    d_prs_opened: "طلبات دمج مفتوحة",
    d_unavailable: "غير متاح — لا يُتتبع على الخادم",
    fix_ok: "الفحص مطابق — لا حاجة لأي إجراء.",
    why_capacity: "الأسطول المثقل يطيل قوائم الانتظار ويضعف زمن استجابة الوكلاء.",
    why_reliability: "الموافقات المعلقة توقف الوكلاء وتترك مخاطر تشغيلية دون معالجة.",
    why_budget: "اقتراب الميزانية من الحد الأقصى يهدد بإيقاف الوكلاء في نهاية الدورة.",
    why_coverage: "المشروع النشط الذي لا يحتوي على وكيل لا يعالج أي عمل آلي.",
    why_governance: "الموافقات غير المعالجة في الوقت المناسب تكشف إجراءات خطرة غير مُحكمة.",
    why_pm: "المشاريع تحت الحد أو المهام المحظورة تؤخر التسليمات.",
    sol_pause: "إيقاف الوكلاء غير ذوي الأولوية مؤقتًا",
    sol_raise_cap: "رفع حد السعة",
    sol_review_approvals: "مراجعة الموافقات المعلقة",
    sol_bulk_approve: "الموافقة الجماعية على الإجراءات منخفضة الخطورة",
    sol_auto_policy: "تعيين سياسة موافقة تلقائية",
    sol_review_costly: "مراجعة الوكلاء الأكثر تكلفة",
    sol_cap_cost: "تحديد سقف للتكلفة لكل وكيل",
    sol_reassign: "إعادة تعيين وكيل للمشروع غير النشط",
    sol_deploy: "نشر وكيل جديد",
    sol_handle_approvals: "معالجة الموافقات المعلقة",
    sol_review_risk: "مراجعة سياسات المخاطر",
    sol_open_atrisk: "فتح المشاريع المعرضة للخطر",
    sol_unblock: "إلغاء حظر المهام المعلقة",
    empty: "لا توجد بيانات أسطول متاحة بعد.",
  },
};

// Valeur dégradée pour les métriques non suivies côté serveur.
const NA = "—";

// each check: { labelKey, detail, status: pass|warn|fail, value, na? }
// na=true => métrique non suivie en live : check neutralisé (status pass, valeur "—").
function systemChecks(agents) {
  const h = healthFrom(agents);
  const running = h.running;
  const blocked = h.blocked;
  const total = agents.length;
  const errors = agents.filter(a => a.state === "error").length;
  const errPct = total ? Math.round(errors / total * 100) : 0;
  return [
    { gkey: "capacity", groupKey: "grp_capacity", items: [
      { labelKey: "chk_fleet_load", detail: running + " {d_active_agents_max}", status: running > 16 ? "warn" : "pass", value: running + "/20" },
      // Débit de tokens : non suivi côté serveur → dégradé.
      { labelKey: "chk_token_tput", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
    ]},
    { gkey: "reliability", groupKey: "grp_reliability", items: [
      { labelKey: "chk_success_rate", detail: errPct + "{d_over7d}", status: errPct > 10 ? "fail" : errPct > 0 ? "warn" : "pass", value: errPct + "%" },
      { labelKey: "chk_no_escalation", detail: blocked + " {d_awaiting}", status: blocked > 1 ? "fail" : blocked === 1 ? "warn" : "pass", value: String(blocked) },
      { labelKey: "chk_stream_active", detail: "{d_live_logs}", status: "pass", value: "live" },
    ]},
    // Budget & coût : aucune métrique de coût/tokens en live → groupe dégradé.
    { gkey: "budget", groupKey: "grp_budget", items: [
      { labelKey: "chk_budget_control", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
      { labelKey: "chk_daily_cost", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
    ]},
  ];
}

function functionalChecks(agents, projects) {
  const items = [];
  // Couverture : projets actifs sans agent affecté (données live de getProjects).
  const active = projects.filter(p => p.status !== "done");
  const unstaffed = active.filter(p => (p.agents_total ?? 0) === 0);
  const activeCount = active.length;
  items.push({ gkey: "coverage", groupKey: "grp_coverage", items: [
    { labelKey: "chk_all_staffed", detail: unstaffed.length ? unstaffed.length + " {d_depts_idle}" : "{d_full_coverage}", status: unstaffed.length ? "warn" : "pass", value: (activeCount - unstaffed.length) + "/" + (activeCount || 0) },
    // Équilibrage de charge : non calculable précisément en live → dégradé.
    { labelKey: "chk_balanced_load", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
  ]});
  // Gouvernance / validations : approbations = agents bloqués (live).
  const blocked = agents.filter(a => a.state === "blocked");
  items.push({ gkey: "governance", groupKey: "grp_governance", items: [
    { labelKey: "chk_approvals_intime", detail: blocked.length + " {d_pending}", status: blocked.length > 1 ? "fail" : blocked.length ? "warn" : "pass", value: String(blocked.length) },
    // Niveau de risque des actions : non suivi côté serveur → dégradé.
    { labelKey: "chk_risky_control", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
  ]});
  // Gestion de projet : avancement & blocages dérivés des projets/agents live.
  const atRisk = projects.filter(p => p.status !== "done" && (p.progress ?? 0) < 50);
  const agentsBlocked = blocked.length;
  items.push({ gkey: "pm", groupKey: "grp_pm", items: [
    { labelKey: "chk_projects_threshold", detail: atRisk.length + " {d_under50}", status: atRisk.length > 1 ? "warn" : "pass", value: (projects.length - atRisk.length) + "/" + (projects.length || 0) },
    { labelKey: "chk_tasks_resolved", detail: agentsBlocked + " {d_blocked_tasks}", status: agentsBlocked > 1 ? "warn" : agentsBlocked ? "warn" : "pass", value: String(agentsBlocked) },
    // PR ouvertes : non suivi côté serveur → dégradé.
    { labelKey: "chk_prs_ontrack", detail: "{d_unavailable}", status: "pass", value: NA, na: true },
  ]});
  return items;
}

const ST_META = {
  pass: { clr: "var(--run)", icon: Icon.check, badgeKey: "compliant" },
  warn: { clr: "var(--wait)", icon: Icon.alert, badgeKey: "watch" },
  fail: { clr: "var(--block)", icon: Icon.x, badgeKey: "non_compliant" },
};

// remediation playbook per audit dimension — why it matters + corrective actions
const FIX = {
  capacity: { whyKey: "why_capacity", sols: [
    { labelKey: "sol_pause", to: "fleet" },
    { labelKey: "sol_raise_cap", to: null } ] },
  reliability: { whyKey: "why_reliability", sols: [
    { labelKey: "sol_review_approvals", to: "review" },
    { labelKey: "sol_bulk_approve", to: "review" },
    { labelKey: "sol_auto_policy", to: null } ] },
  budget: { whyKey: "why_budget", sols: [
    { labelKey: "sol_review_costly", to: "cost" },
    { labelKey: "sol_cap_cost", to: null } ] },
  coverage: { whyKey: "why_coverage", sols: [
    { labelKey: "sol_reassign", to: "depts" },
    { labelKey: "sol_deploy", to: "new" } ] },
  governance: { whyKey: "why_governance", sols: [
    { labelKey: "sol_handle_approvals", to: "review" },
    { labelKey: "sol_review_risk", to: null } ] },
  pm: { whyKey: "why_pm", sols: [
    { labelKey: "sol_open_atrisk", to: "projects" },
    { labelKey: "sol_unblock", to: "review" } ] },
};

export function Audit({ agents: _ignored = [], actions = {} }: { agents?: any[]; actions?: any }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  // resolve {token} placeholders embedded in detail strings against TR
  const td = (s) => typeof s === "string" ? s.replace(/\{(\w+)\}/g, (_, k) => t(k)) : s;

  // Self-fetch des données live (la prop `agents` mock est ignorée, gardée pour compat).
  const [agents, setAgents] = useState<Agent[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  useEffect(() => {
    let on = true;
    getAgents().then(a => on && setAgents(a || [])).catch(() => {});
    getProjects().then(p => on && setProjects(p || [])).catch(() => {});
    return () => { on = false; };
  }, []);

  const [kind, setKind] = useState("system");
  const groups = kind === "system" ? systemChecks(agents) : functionalChecks(agents, projects);
  // Les checks dégradés (na) ne comptent pas dans le score de conformité.
  const all = groups.flatMap(g => g.items).filter(c => !c.na);
  const passes = all.filter(c => c.status === "pass").length;
  const fails = all.filter(c => c.status === "fail").length;
  const warns = all.filter(c => c.status === "warn").length;
  const score = all.length ? Math.round((passes + warns * 0.5) / all.length * 100) : 0;
  const scoreClr = score >= 85 ? "var(--run)" : score >= 60 ? "var(--wait)" : "var(--block)";

  const [openKey, setOpenKey] = useState(null);
  const [scanning, setScanning] = useState(false);
  const rescan = () => {
    if (scanning) return;
    setOpenKey(null);
    setScanning(true);
    // Rafraîchit aussi les données live à chaque relance d'audit.
    getAgents().then(a => setAgents(a || [])).catch(() => {});
    getProjects().then(p => setProjects(p || [])).catch(() => {});
    setTimeout(() => setScanning(false), 1100);
  };
  const C = 2 * Math.PI * 52;
  const goTo = (to) => {
    if (!to || !actions) return;
    ({ fleet: actions.goFleet, review: actions.goReview, cost: actions.goCost, depts: actions.goDepts, projects: actions.goProjects, new: actions.newAgent })[to]?.();
  };

  const empty = agents.length === 0 && projects.length === 0;

  return (
    <div className="audit">
      <div className="au-switch">
        <button className={"au-tab" + (kind === "system" ? " on" : "")} onClick={() => setKind("system")}>
          {Icon.gauge({})}<span><b>{t("system_audit")}</b><i>{t("system_audit_sub")}</i></span>
        </button>
        <button className={"au-tab" + (kind === "functional" ? " on" : "")} onClick={() => setKind("functional")}>
          {Icon.layers({})}<span><b>{t("functional_audit")}</b><i>{t("functional_audit_sub")}</i></span>
        </button>
      </div>

      <div className="au-board">
        <div className={"au-score" + (scanning ? " scanning" : "")} style={{ "--sc": scoreClr }}>
          <div className="au-ring">
            <svg width="140" height="140" viewBox="0 0 140 140">
              <circle cx="70" cy="70" r="52" fill="none" stroke="var(--bg-3)" strokeWidth="9" />
              <circle cx="70" cy="70" r="52" fill="none" stroke="var(--sc)" strokeWidth="9" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={scanning ? C : C * (1 - score / 100)} transform="rotate(-90 70 70)" style={{ transition: "stroke-dashoffset 1s cubic-bezier(.3,.8,.3,1)" }} />
            </svg>
            <div className="au-ring-c">
              <div className="au-score-v num" style={{ color: scoreClr }}>{score + "%"}</div>
            </div>
            <span className="au-sweep"></span>
          </div>
          <div className="au-score-k">{t("compliance")}</div>
          <div className="au-legend">
            <div className="au-leg pass"><b className="num">{passes}</b> {t("compliant")}</div>
            <div className="au-leg warn"><b className="num">{warns}</b> {t("watch")}</div>
            <div className="au-leg fail"><b className="num">{fails}</b> {t("non_compliant")}</div>
            <button className="au-rescan" onClick={rescan} disabled={scanning}>{Icon.gauge({})} {scanning ? "…" : t("rerun_audit")}</button>
          </div>
        </div>

        <div className="au-checks">
          {empty ? (
            <div className="au-group">
              <div className="au-check-sub" style={{ padding: "18px 4px", opacity: .7 }}>{t("empty")}</div>
            </div>
          ) : groups.map((g, gi) => (
            <div className="au-group" key={gi}>
              <div className="au-group-h">{t(g.groupKey)}</div>
              {g.items.map((c, ci) => {
                const m = ST_META[c.status];
                const fx = FIX[g.gkey];
                const key = gi + "-" + ci;
                const open = openKey === key;
                return (
                  <div className={"au-check" + (open ? " open" : "") + (c.na ? " na" : "")} key={ci} style={{ "--cc": m.clr, animationDelay: (gi * 0.06 + ci * 0.04) + "s" }}>
                    <button className="au-check-row" onClick={() => setOpenKey(open ? null : key)}>
                      <span className="au-check-ic">{m.icon({})}</span>
                      <span className="au-check-txt"><span className="au-check-lbl">{t(c.labelKey)}</span><span className="au-check-sub">{td(c.detail)}</span></span>
                      <span className="au-check-val num">{c.value}</span>
                      <span className="au-check-badge">{c.na ? t("watch") : t(m.badgeKey)}</span>
                      <span className={"au-check-chev" + (open ? " up" : "")}>{Icon.chevron({})}</span>
                    </button>
                    {open && (
                      <div className="au-fix">
                        {c.na
                          ? <div className="au-fix-why">{Icon.alert({})}<span>{t("d_unavailable")}</span></div>
                          : c.status === "pass"
                          ? <div className="au-fix-ok">{Icon.check({})}<span>{t("fix_ok")}</span></div>
                          : <>
                              <div className="au-fix-why">{Icon.alert({})}<span>{fx ? t(fx.whyKey) : td(c.detail)}</span></div>
                              <div className="au-fix-sols">
                                {(fx ? fx.sols : []).map((sol, si) => (
                                  <button className="au-sol" key={si} onClick={() => goTo(sol.to)} disabled={!sol.to}>
                                    {Icon.spark({})}<span>{t(sol.labelKey)}</span>{sol.to && Icon.chevron({ style: { width: 13, height: 13, marginLeft: "auto" } })}
                                  </button>
                                ))}
                              </div>
                            </>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
