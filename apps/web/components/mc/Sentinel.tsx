// @ts-nocheck
"use client";

// Sentinel.tsx — "Mr Sultan" : agent sentinelle omniprésent surveillant tout le système.
// Flottant, invocable partout ; détecte les anomalies opérationnelles en LIVE.
// Branché sur les données live de l'API (états problématiques : blocked / error / stale).

import { useState, useEffect } from "react";
import { Icon } from "@/components/mc/icons";
import { getAgents, type Agent } from "@/lib/api";
import { statusOf, fmtAge } from "@/lib/mc";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    title: "Mr Sultan",
    subtitle: "Sentinelle système",
    watching: "Surveille toute la flotte pour anomalies, blocages et silences.",
    grp_blocked: "Agents bloqués",
    grp_error: "Erreurs",
    grp_stale: "Agents silencieux",
    an_blocked: "Agent bloqué, aucune réponse",
    an_error: "Agent en erreur",
    an_stale: "Agent silencieux (heartbeat perdu)",
    no_task: "Tâche inconnue",
    silent_for: "silencieux depuis",
    all_clear: "Tout est en ordre — aucune anomalie détectée.",
    notify: "Notifier l'Exécutif",
    notified: "Exécutif notifié",
    summon: "Invoquer Mr Sultan · J",
  },
  en: {
    title: "Mr Sultan",
    subtitle: "System sentinel",
    watching: "Watching the whole fleet for anomalies, blocks and silences.",
    grp_blocked: "Blocked agents",
    grp_error: "Errors",
    grp_stale: "Silent agents",
    an_blocked: "Agent blocked, no response",
    an_error: "Agent in error",
    an_stale: "Silent agent (heartbeat lost)",
    no_task: "Unknown task",
    silent_for: "silent for",
    all_clear: "All clear — no anomalies detected.",
    notify: "Notify Executive",
    notified: "Executive notified",
    summon: "Summon Mr Sultan · J",
  },
  ar: {
    title: "Mr Sultan",
    subtitle: "حارس النظام",
    watching: "يراقب الأسطول بأكمله بحثًا عن الحالات الشاذة والتوقفات والصمت.",
    grp_blocked: "الوكلاء المتوقفون",
    grp_error: "الأخطاء",
    grp_stale: "الوكلاء الصامتون",
    an_blocked: "الوكيل متوقف، لا استجابة",
    an_error: "الوكيل في حالة خطأ",
    an_stale: "وكيل صامت (فقدان النبض)",
    no_task: "مهمة غير معروفة",
    silent_for: "صامت منذ",
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

// Construit les anomalies LIVE à partir des états problématiques des agents.
// On ne couvre que ce qui est suivi côté serveur : blocked / error / stale.
// Chaque anomalie référence l'agent (clé live `agent`) -> liste cliquable -> onOpenAgent.
function detectAnomalies(agents) {
  const out = [];
  agents
    .filter((a) => a.state === "blocked")
    .forEach((a) =>
      out.push({ grp: "blocked", sev: "fail", agentId: a.agent, titleKey: "an_blocked", agent: a })
    );
  agents
    .filter((a) => a.state === "error")
    .forEach((a) =>
      out.push({ grp: "error", sev: "fail", agentId: a.agent, titleKey: "an_error", agent: a })
    );
  agents
    .filter((a) => a.state === "stale")
    .forEach((a) =>
      out.push({ grp: "stale", sev: "warn", agentId: a.agent, titleKey: "an_stale", agent: a })
    );
  return out;
}

const JGRP = {
  blocked: { labelKey: "grp_blocked", icon: Icon.alert },
  error: { labelKey: "grp_error", icon: Icon.alert },
  stale: { labelKey: "grp_stale", icon: Icon.pulse },
};
const JSEV = { fail: "var(--block)", warn: "var(--wait)", info: "var(--accent)" };

export function Sentinel({ onOpenAgent = () => {}, onNotifyDG = () => {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? TR.en[k] ?? k;
  const [open, setOpen] = useState(false);
  const [notified, setNotified] = useState(false);

  // Self-fetch des agents live.
  const [agents, setAgents] = useState<Agent[]>([]);
  useEffect(() => {
    let on = true;
    getAgents()
      .then((a) => on && setAgents(a))
      .catch(() => {});
    return () => {
      on = false;
    };
  }, []);

  const anomalies = detectAnomalies(agents);
  const groups = ["blocked", "error", "stale"]
    .map((g) => ({ g, items: anomalies.filter((a) => a.grp === g) }))
    .filter((x) => x.items.length);

  // Titre visible = libellé traduit de l'anomalie.
  const anomalyTitle = (a) => t(a.titleKey);
  // Détail visible = libellé de l'agent live + blocage/tâche + âge du silence.
  const anomalyDetail = (a) => {
    const ag = a.agent;
    const parts = [];
    const name = ag.label || ag.agent;
    if (name) parts.push(name);
    // raison : blocker prioritaire (blocked), sinon la tâche courante.
    const reason = ag.blocker || ag.task;
    if (reason) parts.push(reason);
    else parts.push(t("no_task"));
    // âge (silence) — utile surtout pour stale.
    if (a.grp === "stale" && ag.age_seconds != null) {
      parts.push(t("silent_for") + " " + fmtAge(ag.age_seconds));
    } else if (ag.age_seconds != null) {
      parts.push(fmtAge(ag.age_seconds));
    }
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
