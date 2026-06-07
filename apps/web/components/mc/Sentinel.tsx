"use client";
// @ts-nocheck

// Sentinel.tsx — "Mr Sultan": an omnipresent sentinel agent watching the whole system.
// Floating, summonable anywhere; detects anomalies/bugs/intrusions; can alert the Executive.
// Porté depuis le design mc-joker.jsx — rendu statique sur les données mock.

import { useState } from "react";
import { Icon } from "@/components/mc/icons";
import { AGENTS, STATUS, fmtCost } from "@/lib/mc-data";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    title: "Mr Sultan",
    subtitle: "Sentinelle système",
    watching: "Surveille toute la flotte pour anomalies, bugs et intrusions.",
    grp_ops: "Anomalies opérationnelles",
    grp_sec: "Sécurité & intrusion",
    grp_coh: "Cohérence & coût",
    an_blocked: "Agent bloqué, aucune réponse",
    an_high_risk: "Action à haut risque en attente",
    an_intrusion: "Tentative d'accès inhabituelle filtrée",
    an_blocked_tasks: "tâche(s) bloquée(s) dans le pipeline",
    an_budget: "Dérive budgétaire détectée",
    approval_required: "validation requise",
    intrusion_detail_a: "3 requêtes hors périmètre bloquées sur",
    deps_detail: "Dépendances non résolues entre étapes",
    budget_detail_a: "% du budget mensuel utilisé",
    all_clear: "Tout est en ordre — aucune anomalie détectée.",
    notify: "Notifier l'Exécutif",
    notified: "Exécutif notifié",
    summon: "Invoquer Mr Sultan · J",
  },
  en: {
    title: "Mr Sultan",
    subtitle: "System sentinel",
    watching: "Watching the whole fleet for anomalies, bugs and intrusions.",
    grp_ops: "Operational anomalies",
    grp_sec: "Security & intrusion",
    grp_coh: "Coherence & cost",
    an_blocked: "Agent blocked, no response",
    an_high_risk: "High-risk action pending",
    an_intrusion: "Unusual access attempt filtered",
    an_blocked_tasks: "blocked task(s) in the pipeline",
    an_budget: "Budget drift detected",
    approval_required: "approval required",
    intrusion_detail_a: "3 out-of-scope requests blocked on",
    deps_detail: "Unresolved dependencies between steps",
    budget_detail_a: "% of monthly budget used",
    all_clear: "All clear — no anomalies detected.",
    notify: "Notify Executive",
    notified: "Executive notified",
    summon: "Summon Mr Sultan · J",
  },
  ar: {
    title: "Mr Sultan",
    subtitle: "حارس النظام",
    watching: "يراقب الأسطول بأكمله بحثًا عن الحالات الشاذة والأخطاء والاختراقات.",
    grp_ops: "حالات شاذة تشغيلية",
    grp_sec: "الأمن والاختراق",
    grp_coh: "الاتساق والتكلفة",
    an_blocked: "الوكيل متوقف، لا استجابة",
    an_high_risk: "إجراء عالي الخطورة قيد الانتظار",
    an_intrusion: "تمت تصفية محاولة وصول غير معتادة",
    an_blocked_tasks: "مهمة (مهام) متوقفة في خط المعالجة",
    an_budget: "تم رصد انحراف في الميزانية",
    approval_required: "الموافقة مطلوبة",
    intrusion_detail_a: "تم حظر 3 طلبات خارج النطاق على",
    deps_detail: "تبعيات غير محلولة بين الخطوات",
    budget_detail_a: "٪ من الميزانية الشهرية مستخدَمة",
    all_clear: "كل شيء على ما يرام — لم يتم رصد أي حالات شاذة.",
    notify: "إبلاغ الإدارة التنفيذية",
    notified: "تم إبلاغ الإدارة التنفيذية",
    summon: "استدعاء Mr Sultan · J",
  },
};

// the sentinel mascot — a robot with a scanning visor + jester antenna
function JokerFace({ size = 30, scanning = false }) {
  return (
    <svg className={"joker-face" + (scanning ? " scan" : "")} width={size} height={size} viewBox="0 0 40 40" fill="none" style={{ display: "block", overflow: "visible" }} aria-hidden="true">
      {/* jester antenna: 3 prongs with balls */}
      <g stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
        <path d="M20 8 V4" /><circle cx="20" cy="2.6" r="1.5" fill="currentColor" stroke="none" />
        <path d="M13.5 9 L10.5 5.5" /><circle cx="10" cy="5" r="1.3" fill="currentColor" stroke="none" />
        <path d="M26.5 9 L29.5 5.5" /><circle cx="30" cy="5" r="1.3" fill="currentColor" stroke="none" />
      </g>
      {/* head */}
      <rect x="9" y="9" width="22" height="18" rx="7" fill="currentColor" fillOpacity=".16" stroke="currentColor" strokeWidth="1.8" />
      {/* visor band */}
      <rect x="12" y="15" width="16" height="6" rx="3" fill="currentColor" fillOpacity=".25" />
      {/* scanning eye */}
      <circle className="joker-eye" cx="20" cy="18" r="2.2" fill="currentColor" stroke="none" />
      {/* mouth grin */}
      <path d="M15.5 23 q4.5 3 9 0" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      {/* shoulders */}
      <path d="M8 34 q0-5 5-5.6 h14 q5 .6 5 5.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Returns anomalies with translation keys; visible strings are resolved via t() in the JSX.
// titleKey  -> key in TR for the anomaly title
// detail    -> non-translatable parts (agent name, repo, sha…) — may be null
// detailKey -> key in TR for a translatable detail suffix — may be null
function detectAnomalies(agents) {
  const out = [];
  const byId = {};
  agents.forEach((a) => (byId[a.id] = a));
  // operational
  agents
    .filter((a) => a.status === "blocked")
    .forEach((a) =>
      out.push({
        grp: "ops",
        sev: "fail",
        agentId: a.id,
        titleKey: "an_blocked",
        detail: a.name,
        detailKey: a.pendingAction ? null : "approval_required",
        detailExtra: a.pendingAction ? a.pendingAction.title : null,
      })
    );
  // security / intrusion
  agents
    .filter((a) => a.pendingAction && a.pendingAction.risk === "high")
    .forEach((a) =>
      out.push({
        grp: "sec",
        sev: "fail",
        agentId: a.id,
        titleKey: "an_high_risk",
        detail: a.name,
        detailExtra: a.pendingAction.title,
      })
    );
  // synthesized intrusion signal (sentinel flavour, deterministic)
  const sec = byId["a-sec"];
  if (sec)
    out.push({
      grp: "sec",
      sev: "warn",
      agentId: "a-sec",
      titleKey: "an_intrusion",
      detailKey: "intrusion_detail_a",
      detail: sec.repo,
    });
  // bugs / inconsistencies
  const tasksBlocked = agents.reduce((s, a) => s + (a.steps || []).filter((t) => t.blocked).length, 0);
  if (tasksBlocked)
    out.push({
      grp: "coh",
      sev: "warn",
      titleNum: tasksBlocked,
      titleKey: "an_blocked_tasks",
      detailKey: "deps_detail",
    });
  const cost = agents.reduce((s, a) => s + a.cost, 0);
  const budgetPct = Math.round((cost * 26) / 1200 * 100);
  if (budgetPct > 75)
    out.push({
      grp: "coh",
      sev: budgetPct > 90 ? "fail" : "warn",
      titleKey: "an_budget",
      detailNum: budgetPct,
      detailKey: "budget_detail_a",
    });
  return out;
}

const JGRP = {
  ops: { labelKey: "grp_ops", icon: Icon.pulse },
  sec: { labelKey: "grp_sec", icon: Icon.layers },
  coh: { labelKey: "grp_coh", icon: Icon.alert },
};
const JSEV = { fail: "var(--block)", warn: "var(--wait)", info: "var(--accent)" };

export function Sentinel({ onOpenAgent = () => {}, onNotifyDG = () => {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? TR.en[k] ?? k;
  const [open, setOpen] = useState(false);
  const [notified, setNotified] = useState(false);
  const agents = AGENTS;
  const anomalies = detectAnomalies(agents);
  const groups = ["ops", "sec", "coh"]
    .map((g) => ({ g, items: anomalies.filter((a) => a.grp === g) }))
    .filter((x) => x.items.length);

  // Compose a visible title from an anomaly's translation key + optional leading number.
  const anomalyTitle = (a) =>
    (a.titleNum != null ? a.titleNum + " " : "") + t(a.titleKey);
  // Compose a visible detail: dynamic parts (names/repos — not translated) + translatable suffix.
  const anomalyDetail = (a) => {
    if (a.titleKey === "an_intrusion") return t("intrusion_detail_a") + " " + a.detail;
    if (a.detailNum != null) return a.detailNum + t("budget_detail_a");
    const parts = [];
    if (a.detail) parts.push(a.detail);
    if (a.detailExtra) parts.push(a.detailExtra);
    if (a.detailKey) parts.push(t(a.detailKey));
    return parts.join(" · ");
  };

  const notify = () => {
    setNotified(true);
    onNotifyDG(anomalies.length);
  };

  return (
    <div className="joker">
      {open && (
        <div className="joker-panel" role="dialog" aria-label="Mr Sultan">
          <div className="joker-head">
            <span className="joker-badge-ic">
              <JokerFace size={30} />
            </span>
            <div className="joker-h-txt">
              <b>{t("title")}</b>
              <i>{t("subtitle")}</i>
            </div>
            <button className="joker-x btn ghost icon" onClick={() => setOpen(false)}>
              {Icon.x({})}
            </button>
          </div>
          <div className="joker-sub">{t("watching")}</div>

          {anomalies.length === 0 ? (
            <div className="joker-clear">
              {Icon.check({})}
              <span>{t("all_clear")}</span>
            </div>
          ) : (
            <div className="joker-list">
              {groups.map(({ g, items }) => (
                <div className="joker-grp" key={g}>
                  <div className="joker-grp-h">
                    {JGRP[g].icon({})} {t(JGRP[g].labelKey)} <span className="joker-grp-n">{items.length}</span>
                  </div>
                  {items.map((a, i) => (
                    <button
                      className="joker-item"
                      key={i}
                      style={{ "--jc": JSEV[a.sev] }}
                      onClick={() => a.agentId && (onOpenAgent(a.agentId), setOpen(false))}
                      disabled={!a.agentId}
                    >
                      <span className="joker-dot"></span>
                      <span className="joker-item-txt">
                        <span className="joker-item-t">{anomalyTitle(a)}</span>
                        <span className="joker-item-d">{anomalyDetail(a)}</span>
                      </span>
                      {a.agentId && <span className="joker-item-go">{Icon.chevron({})}</span>}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}

          <button className={"joker-notify" + (notified ? " done" : "")} onClick={notify} disabled={notified}>
            {notified ? Icon.check({}) : Icon.spark({})} {notified ? t("notified") : t("notify")}
          </button>
        </div>
      )}
      <button
        className={"joker-fab" + (anomalies.length ? " alert" : "") + (open ? " open" : "")}
        onClick={() => setOpen((o) => !o)}
        title={t("summon")}
        aria-label={t("title")}
      >
        <span className="joker-fab-glow"></span>
        <JokerFace size={34} />
        {anomalies.length > 0 && <span className="joker-fab-badge">{anomalies.length}</span>}
      </button>
    </div>
  );
}
