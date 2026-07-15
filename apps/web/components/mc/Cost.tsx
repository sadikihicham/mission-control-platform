// @ts-nocheck
"use client";

// Cost.tsx — Coûts & usage : aucun suivi de coût/tokens n'existe côté serveur
// (ni par agent, ni par projet, ni de budget). Plutôt que d'inventer une
// métrique de substitution, cette vue affiche honnêtement des indicateurs
// non disponibles — voir CLAUDE.md / CONTRACTS.md.

import { Icon } from "@/components/mc/icons";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    "cost_per_day": "Coût par jour",
    "total_cost": "Coût total",
    "total_tokens": "Total tokens",
    "avg_day": "Moy. / jour",
    "not_available": "Indisponible — non suivi côté serveur",
    "not_tracked_title": "Suivi des coûts",
    "not_tracked_body": "Le suivi des coûts et de l'usage n'est pas encore implémenté côté serveur — ces indicateurs s'activeront une fois la télémétrie de coût/tokens branchée sur l'API.",
  },
  en: {
    "cost_per_day": "Cost per day",
    "total_cost": "Total cost",
    "total_tokens": "Total tokens",
    "avg_day": "Avg / day",
    "not_available": "Unavailable — not tracked server-side",
    "not_tracked_title": "Cost tracking",
    "not_tracked_body": "Cost and usage tracking isn't implemented server-side yet — these indicators will activate once cost/token telemetry is wired to the API.",
  },
  ar: {
    "cost_per_day": "التكلفة اليومية",
    "total_cost": "إجمالي التكلفة",
    "total_tokens": "إجمالي الرموز",
    "avg_day": "المعدل / يوم",
    "not_available": "غير متاح — لا يُتتبع على الخادم",
    "not_tracked_title": "تتبع التكاليف",
    "not_tracked_body": "لم يتم بعد تفعيل تتبع التكاليف والاستخدام على الخادم — ستُفعَّل هذه المؤشرات بمجرد ربط قياس التكلفة/الرموز بواجهة البرمجة.",
  },
};

export function Cost() {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const NA_TITLE = tt("not_available");

  return (
    <div className="cost">
      <div className="cost-kpis">
        <div className="ck">
          <div className="ck-k">{Icon.coin({})} {tt("cost_per_day")}</div>
          <div className="ck-v num" title={NA_TITLE}>—</div>
        </div>
        <div className="ck">
          <div className="ck-k">{Icon.coin({})} {tt("total_cost")}</div>
          <div className="ck-v num" title={NA_TITLE}>—</div>
        </div>
        <div className="ck">
          <div className="ck-k">{Icon.bolt({})} {tt("total_tokens")}</div>
          <div className="ck-v num" title={NA_TITLE}>—</div>
        </div>
        <div className="ck">
          <div className="ck-k">{Icon.gauge({})} {tt("avg_day")}</div>
          <div className="ck-v num" title={NA_TITLE}>—</div>
        </div>
      </div>

      <section className="cc-card">
        <div className="cc-head">
          <h2>{Icon.alert({})} {tt("not_tracked_title")}</h2>
        </div>
        <p style={{ color: "var(--tx-mid)", fontSize: 13.5, lineHeight: 1.55, margin: 0 }}>
          {tt("not_tracked_body")}
        </p>
      </section>
    </div>
  );
}
