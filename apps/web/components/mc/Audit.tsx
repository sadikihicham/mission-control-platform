"use client";
// @ts-nocheck
import { useState } from "react";
import { Icon } from "@/components/mc/icons";
import { STATUS, fmtCost, fmtTok } from "@/lib/mc-data";
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
    chk_success_rate: "Taux de succès des agents",
    chk_no_escalation: "Aucune escalade non traitée",
    chk_stream_active: "Flux temps réel actif",
    chk_budget_control: "Budget mensuel sous contrôle",
    chk_daily_cost: "Coût quotidien stable",
    chk_all_staffed: "Tous les départements opérationnels dotés",
    chk_balanced_load: "Charge équilibrée entre départements",
    chk_approvals_intime: "Approbations humaines traitées à temps",
    chk_risky_control: "Actions risquées sous contrôle",
    chk_projects_threshold: "Projets au-dessus du seuil d'avancement",
    chk_tasks_resolved: "Tâches bloquées résolues",
    chk_prs_ontrack: "Livraisons (PR) dans les temps",
    d_active_agents_max: "agents actifs / 20 max",
    d_total: "total",
    d_over7d: "% sur 7 jours",
    d_awaiting: "agent(s) en attente d'approbation",
    d_live_logs: "Journaux & métriques en direct",
    d_used: "% utilisé",
    d_per_day: "/ jour",
    d_full_coverage: "Couverture complète",
    d_depts_idle: "département(s) inactif(s)",
    d_max_gap: "Écart max 2 agents",
    d_pending: "en attente",
    d_high_risk: "à haut risque",
    d_under50: "projet(s) sous 50%",
    d_blocked_tasks: "tâche(s) bloquée(s)",
    d_prs_opened: "PR ouvertes",
    fix_ok: "Contrôle conforme — aucune action requise.",
    why_capacity: "Une flotte surchargée allonge les files d'attente et dégrade la latence des agents.",
    why_reliability: "Les approbations en attente bloquent les agents et laissent un risque opérationnel non traité.",
    why_budget: "Un budget proche du plafond risque d'arrêter les agents en fin de cycle.",
    why_coverage: "Un département sans agent ne traite aucun travail automatisé.",
    why_governance: "Des approbations non traitées à temps exposent des actions risquées non maîtrisées.",
    why_pm: "Des projets sous le seuil ou des tâches bloquées retardent les livraisons.",
    sol_pause: "Mettre en pause les agents non prioritaires",
    sol_raise_cap: "Augmenter le plafond de capacité",
    sol_review_approvals: "Examiner les approbations en attente",
    sol_bulk_approve: "Approuver en masse les actions à faible risque",
    sol_auto_policy: "Définir une politique d'auto-approbation",
    sol_review_costly: "Examiner les agents les plus coûteux",
    sol_cap_cost: "Plafonner le coût par agent",
    sol_reassign: "Réaffecter un agent au département inactif",
    sol_deploy: "Déployer un nouvel agent",
    sol_handle_approvals: "Traiter les approbations en attente",
    sol_review_risk: "Examiner les politiques de risque",
    sol_open_atrisk: "Ouvrir les projets à risque",
    sol_unblock: "Débloquer les tâches en attente",
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
    grp_coverage: "Department coverage",
    grp_governance: "Governance & approvals",
    grp_pm: "Project management",
    chk_fleet_load: "Fleet load under threshold",
    chk_token_tput: "Token throughput nominal",
    chk_success_rate: "Agent success rate",
    chk_no_escalation: "No unhandled escalation",
    chk_stream_active: "Real-time stream active",
    chk_budget_control: "Monthly budget under control",
    chk_daily_cost: "Daily cost stable",
    chk_all_staffed: "All operating departments staffed",
    chk_balanced_load: "Balanced load across departments",
    chk_approvals_intime: "Human approvals handled in time",
    chk_risky_control: "Risky actions under control",
    chk_projects_threshold: "Projects above completion threshold",
    chk_tasks_resolved: "Blocked tasks resolved",
    chk_prs_ontrack: "Deliveries (PRs) on track",
    d_active_agents_max: "active agents / 20 max",
    d_total: "total",
    d_over7d: "% over 7 days",
    d_awaiting: "agent(s) awaiting approval",
    d_live_logs: "Live logs & metrics",
    d_used: "% used",
    d_per_day: "/ day",
    d_full_coverage: "Full coverage",
    d_depts_idle: "department(s) idle",
    d_max_gap: "Max gap 2 agents",
    d_pending: "pending",
    d_high_risk: "high-risk",
    d_under50: "project(s) under 50%",
    d_blocked_tasks: "blocked task(s)",
    d_prs_opened: "PRs opened",
    fix_ok: "Check compliant — no action required.",
    why_capacity: "An overloaded fleet lengthens queues and degrades agent latency.",
    why_reliability: "Pending approvals stall agents and leave operational risk unhandled.",
    why_budget: "A budget near the cap risks halting agents at cycle end.",
    why_coverage: "A department with no agent handles no automated work.",
    why_governance: "Approvals not handled in time expose uncontrolled risky actions.",
    why_pm: "Projects under threshold or blocked tasks delay deliveries.",
    sol_pause: "Pause non-priority agents",
    sol_raise_cap: "Raise the capacity cap",
    sol_review_approvals: "Review pending approvals",
    sol_bulk_approve: "Bulk-approve low-risk actions",
    sol_auto_policy: "Set an auto-approval policy",
    sol_review_costly: "Review the costliest agents",
    sol_cap_cost: "Cap cost per agent",
    sol_reassign: "Reassign an agent to the idle department",
    sol_deploy: "Deploy a new agent",
    sol_handle_approvals: "Handle pending approvals",
    sol_review_risk: "Review risk policies",
    sol_open_atrisk: "Open at-risk projects",
    sol_unblock: "Unblock pending tasks",
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
    grp_coverage: "تغطية الأقسام",
    grp_governance: "الحوكمة والموافقات",
    grp_pm: "إدارة المشاريع",
    chk_fleet_load: "حمل الأسطول تحت الحد الأقصى",
    chk_token_tput: "معدل تدفق الرموز طبيعي",
    chk_success_rate: "معدل نجاح الوكلاء",
    chk_no_escalation: "لا توجد تصعيدات غير معالجة",
    chk_stream_active: "البث في الوقت الفعلي نشط",
    chk_budget_control: "الميزانية الشهرية تحت السيطرة",
    chk_daily_cost: "التكلفة اليومية مستقرة",
    chk_all_staffed: "جميع الأقسام التشغيلية مزودة بالوكلاء",
    chk_balanced_load: "حمل متوازن عبر الأقسام",
    chk_approvals_intime: "معالجة الموافقات البشرية في الوقت المناسب",
    chk_risky_control: "الإجراءات الخطرة تحت السيطرة",
    chk_projects_threshold: "المشاريع فوق حد الإنجاز",
    chk_tasks_resolved: "حل المهام المحظورة",
    chk_prs_ontrack: "التسليمات (طلبات الدمج) في الموعد",
    d_active_agents_max: "وكلاء نشطون / 20 كحد أقصى",
    d_total: "الإجمالي",
    d_over7d: "٪ خلال 7 أيام",
    d_awaiting: "وكيل (وكلاء) في انتظار الموافقة",
    d_live_logs: "السجلات والمقاييس المباشرة",
    d_used: "٪ مستخدم",
    d_per_day: "/ يوم",
    d_full_coverage: "تغطية كاملة",
    d_depts_idle: "قسم (أقسام) غير نشط",
    d_max_gap: "أقصى فجوة وكيلان",
    d_pending: "قيد الانتظار",
    d_high_risk: "عالي الخطورة",
    d_under50: "مشروع (مشاريع) تحت 50٪",
    d_blocked_tasks: "مهمة (مهام) محظورة",
    d_prs_opened: "طلبات دمج مفتوحة",
    fix_ok: "الفحص مطابق — لا حاجة لأي إجراء.",
    why_capacity: "الأسطول المثقل يطيل قوائم الانتظار ويضعف زمن استجابة الوكلاء.",
    why_reliability: "الموافقات المعلقة توقف الوكلاء وتترك مخاطر تشغيلية دون معالجة.",
    why_budget: "اقتراب الميزانية من الحد الأقصى يهدد بإيقاف الوكلاء في نهاية الدورة.",
    why_coverage: "القسم الذي لا يحتوي على وكيل لا يعالج أي عمل آلي.",
    why_governance: "الموافقات غير المعالجة في الوقت المناسب تكشف إجراءات خطرة غير مُحكمة.",
    why_pm: "المشاريع تحت الحد أو المهام المحظورة تؤخر التسليمات.",
    sol_pause: "إيقاف الوكلاء غير ذوي الأولوية مؤقتًا",
    sol_raise_cap: "رفع حد السعة",
    sol_review_approvals: "مراجعة الموافقات المعلقة",
    sol_bulk_approve: "الموافقة الجماعية على الإجراءات منخفضة الخطورة",
    sol_auto_policy: "تعيين سياسة موافقة تلقائية",
    sol_review_costly: "مراجعة الوكلاء الأكثر تكلفة",
    sol_cap_cost: "تحديد سقف للتكلفة لكل وكيل",
    sol_reassign: "إعادة تعيين وكيل للقسم غير النشط",
    sol_deploy: "نشر وكيل جديد",
    sol_handle_approvals: "معالجة الموافقات المعلقة",
    sol_review_risk: "مراجعة سياسات المخاطر",
    sol_open_atrisk: "فتح المشاريع المعرضة للخطر",
    sol_unblock: "إلغاء حظر المهام المعلقة",
  },
};

// department → agent ids (mirror of mc-depts)
const DEPT_MAP = { dg: ["a-perf", "a-docs"], finance: ["a-checkout", "a-tests"], ventes: ["a-react", "a-dark"], marketing: ["a-i18n", "a-images"], hr: ["a-sec", "a-auth"], achats: ["a-migrate"], logistique: ["a-ci"], stock: [] };

// each check: { label, detail, status: pass|warn|fail, value }
function systemChecks(agents) {
  const running = agents.filter(a => a.status === "running").length;
  const blocked = agents.filter(a => a.status === "blocked").length;
  const cost = agents.reduce((s, a) => s + a.cost, 0);
  const budgetPct = Math.min(100, Math.round(cost * 26 / 1200 * 100));
  const tok = agents.reduce((s, a) => s + a.tokensIn + a.tokensOut, 0);
  const success = 94;
  return [
    { gkey: "capacity", groupKey: "grp_capacity", items: [
      { labelKey: "chk_fleet_load", detail: running + " {d_active_agents_max}", status: running > 16 ? "warn" : "pass", value: running + "/20" },
      { labelKey: "chk_token_tput", detail: fmtTok(tok) + " {d_total}", status: "pass", value: fmtTok(tok) },
    ]},
    { gkey: "reliability", groupKey: "grp_reliability", items: [
      { labelKey: "chk_success_rate", detail: success + "{d_over7d}", status: success >= 90 ? "pass" : "warn", value: success + "%" },
      { labelKey: "chk_no_escalation", detail: blocked + " {d_awaiting}", status: blocked > 1 ? "fail" : blocked === 1 ? "warn" : "pass", value: String(blocked) },
      { labelKey: "chk_stream_active", detail: "{d_live_logs}", status: "pass", value: "live" },
    ]},
    { gkey: "budget", groupKey: "grp_budget", items: [
      { labelKey: "chk_budget_control", detail: budgetPct + "{d_used}", status: budgetPct > 90 ? "fail" : budgetPct > 75 ? "warn" : "pass", value: budgetPct + "%" },
      { labelKey: "chk_daily_cost", detail: fmtCost(cost) + " {d_per_day}", status: "pass", value: fmtCost(cost) },
    ]},
  ];
}

function functionalChecks(agents) {
  const items = [];
  // departments coverage
  const idle = Object.entries(DEPT_MAP).filter(([k, ids]) => ids.length === 0);
  items.push({ gkey: "coverage", groupKey: "grp_coverage", items: [
    { labelKey: "chk_all_staffed", detail: idle.length ? idle.length + " {d_depts_idle}" : "{d_full_coverage}", status: idle.length > 1 ? "warn" : idle.length === 1 ? "warn" : "pass", value: (8 - idle.length) + "/8" },
    { labelKey: "chk_balanced_load", detail: "{d_max_gap}", status: "pass", value: "OK" },
  ]});
  // governance / validations
  const blocked = agents.filter(a => a.status === "blocked");
  items.push({ gkey: "governance", groupKey: "grp_governance", items: [
    { labelKey: "chk_approvals_intime", detail: blocked.length + " {d_pending}", status: blocked.length > 1 ? "fail" : blocked.length ? "warn" : "pass", value: String(blocked.length) },
    { labelKey: "chk_risky_control", detail: blocked.filter(a => a.pendingAction && a.pendingAction.risk === "high").length + " {d_high_risk}", status: blocked.some(a => a.pendingAction && a.pendingAction.risk === "high") ? "warn" : "pass", value: "—" },
  ]});
  // project management
  const repos = {};
  agents.forEach(a => { (repos[a.repo] = repos[a.repo] || []).push(a); });
  const atRisk = Object.entries(repos).filter(([r, its]) => { const td = its.reduce((s, a) => s + (a.steps || []).filter(t => t.done).length, 0); const tt = its.reduce((s, a) => s + (a.steps || []).length, 0); return tt && td / tt < 0.5; });
  const tasksBlocked = agents.reduce((s, a) => s + (a.steps || []).filter(t => t.blocked).length, 0);
  items.push({ gkey: "pm", groupKey: "grp_pm", items: [
    { labelKey: "chk_projects_threshold", detail: atRisk.length + " {d_under50}", status: atRisk.length > 1 ? "warn" : "pass", value: (Object.keys(repos).length - atRisk.length) + "/" + Object.keys(repos).length },
    { labelKey: "chk_tasks_resolved", detail: tasksBlocked + " {d_blocked_tasks}", status: tasksBlocked > 1 ? "warn" : tasksBlocked ? "warn" : "pass", value: String(tasksBlocked) },
    { labelKey: "chk_prs_ontrack", detail: agents.filter(a => a.pr).length + " {d_prs_opened}", status: "pass", value: String(agents.filter(a => a.pr).length) },
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

export function Audit({ agents = [], actions = {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  // resolve {token} placeholders embedded in detail strings against TR
  const td = (s) => typeof s === "string" ? s.replace(/\{(\w+)\}/g, (_, k) => t(k)) : s;
  const [kind, setKind] = useState("system");
  const groups = (kind === "system" ? systemChecks : functionalChecks)(agents);
  const all = groups.flatMap(g => g.items);
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
    setTimeout(() => setScanning(false), 1100);
  };
  const C = 2 * Math.PI * 52;
  const goTo = (to) => {
    if (!to || !actions) return;
    ({ fleet: actions.goFleet, review: actions.goReview, cost: actions.goCost, depts: actions.goDepts, projects: actions.goProjects, new: actions.newAgent })[to]?.();
  };

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
          {groups.map((g, gi) => (
            <div className="au-group" key={gi}>
              <div className="au-group-h">{t(g.groupKey)}</div>
              {g.items.map((c, ci) => {
                const m = ST_META[c.status];
                const fx = FIX[g.gkey];
                const key = gi + "-" + ci;
                const open = openKey === key;
                return (
                  <div className={"au-check" + (open ? " open" : "")} key={ci} style={{ "--cc": m.clr, animationDelay: (gi * 0.06 + ci * 0.04) + "s" }}>
                    <button className="au-check-row" onClick={() => setOpenKey(open ? null : key)}>
                      <span className="au-check-ic">{m.icon({})}</span>
                      <span className="au-check-txt"><span className="au-check-lbl">{t(c.labelKey)}</span><span className="au-check-sub">{td(c.detail)}</span></span>
                      <span className="au-check-val num">{c.value}</span>
                      <span className="au-check-badge">{t(m.badgeKey)}</span>
                      <span className={"au-check-chev" + (open ? " up" : "")}>{Icon.chevron({})}</span>
                    </button>
                    {open && (
                      <div className="au-fix">
                        {c.status === "pass"
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
