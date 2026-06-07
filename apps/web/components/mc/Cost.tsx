"use client";
// @ts-nocheck

import { Icon } from "@/components/mc/icons";
import { Robot } from "@/components/mc/Robot";
import { AGENTS, STATUS, fmtCost, fmtTok } from "@/lib/mc-data";
import { useI18n } from "@/lib/i18n";

const TR = {
  fr: {
    "cost_per_day": "Coût par jour",
    "total_cost": "Coût total",
    "total_tokens": "Total tokens",
    "avg_day": "Moy. / jour",
    "spend_7d": "Dépenses · 7 jours",
    "by_project": "Par projet",
    "top_agents": "Top agents",
    "budget": "Budget",
    "remaining": "% restant",
    "used": "% utilisé",
    "today": "Auj.",
  },
  en: {
    "cost_per_day": "Cost per day",
    "total_cost": "Total cost",
    "total_tokens": "Total tokens",
    "avg_day": "Avg / day",
    "spend_7d": "Spend · 7 days",
    "by_project": "By project",
    "top_agents": "Top agents",
    "budget": "Budget",
    "remaining": "% remaining",
    "used": "% used",
    "today": "Today",
  },
  ar: {
    "cost_per_day": "التكلفة اليومية",
    "total_cost": "إجمالي التكلفة",
    "total_tokens": "إجمالي الرموز",
    "avg_day": "المعدل / يوم",
    "spend_7d": "الإنفاق · 7 أيام",
    "by_project": "حسب المشروع",
    "top_agents": "أبرز الوكلاء",
    "budget": "الميزانية",
    "remaining": "٪ متبقٍ",
    "used": "٪ مستخدَم",
    "today": "اليوم",
  },
};

const PMETA = { "acme/api": "AP", "acme/web": "WB", "acme/dashboard": "DB", "acme/payments": "PY", "acme/analytics": "AN" };
const PHUE = { "acme/api": "#d97757", "acme/web": "#6b8cff", "acme/dashboard": "#b07ae8", "acme/payments": "#3fb6a8", "acme/analytics": "#e0a23f" };

// deterministic 7-day series shaped around the live daily total
function series7(today) {
  const w = [0.62, 0.78, 0.7, 0.95, 1.12, 0.88, 1];
  return w.map((f) => Math.round(today * f * 100) / 100);
}

function AreaChart({ data, labels, color }) {
  const W = 720, H = 200, pad = 28;
  const max = Math.max(...data) * 1.15 || 1;
  const x = (i) => pad + (i * (W - pad * 2)) / (data.length - 1);
  const y = (v) => H - pad - (v / max) * (H - pad * 2);
  const pts = data.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${pad},${H - pad} ${pts} ${W - pad},${H - pad}`;
  return (
    <svg className="cc-area" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 200 }}>
      <defs><linearGradient id="ccg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".34" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      {[0, 0.5, 1].map((g) => <line key={g} x1={pad} x2={W - pad} y1={pad + g * (H - pad * 2)} y2={pad + g * (H - pad * 2)} stroke="var(--border-soft)" strokeWidth="1" />)}
      <polygon points={area} fill="url(#ccg)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {data.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={i === data.length - 1 ? 5 : 3} fill={i === data.length - 1 ? color : "var(--bg-0)"} stroke={color} strokeWidth="2" />)}
      {labels.map((l, i) => <text key={i} x={x(i)} y={H - 6} fill="var(--tx-lo)" fontSize="12" fontFamily="var(--mono)" textAnchor="middle">{l}</text>)}
    </svg>
  );
}

export function Cost({ agents = AGENTS, totalCost = 0 }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const totalAll = agents.reduce((s, a) => s + a.cost, 0);
  const tokensAll = agents.reduce((s, a) => s + a.tokensIn + a.tokensOut, 0);
  const data = series7(totalCost || totalAll);
  const labels = ["D-6", "D-5", "D-4", "D-3", "D-2", "D-1", tt("today")];
  const avg = data.reduce((s, v) => s + v, 0) / data.length;

  // cost by project
  const byProj = {};
  agents.forEach((a) => { byProj[a.repo] = (byProj[a.repo] || 0) + a.cost; });
  const projects = Object.entries(byProj).map(([repo, cost]) => ({ repo, cost })).sort((a, b) => b.cost - a.cost);
  const projMax = Math.max(...projects.map((p) => p.cost), 0.01);

  // top agents
  const top = [...agents].sort((a, b) => b.cost - a.cost).slice(0, 6);
  const topMax = Math.max(...top.map((a) => a.cost), 0.01);

  // budget
  const budget = 1200, used = Math.round(totalAll * 26);
  const usedPct = Math.min(100, Math.round((used / budget) * 100));

  return (
    <div className="cost">
      <div className="cost-kpis">
        <div className="ck"><div className="ck-k">{Icon.coin({})} {tt("cost_per_day")}</div><div className="ck-v num">{fmtCost(totalCost || totalAll)}</div></div>
        <div className="ck"><div className="ck-k">{Icon.coin({})} {tt("total_cost")}</div><div className="ck-v num">{fmtCost(totalAll)}</div></div>
        <div className="ck"><div className="ck-k">{Icon.bolt({})} {tt("total_tokens")}</div><div className="ck-v num">{fmtTok(tokensAll)}</div></div>
        <div className="ck"><div className="ck-k">{Icon.gauge({})} {tt("avg_day")}</div><div className="ck-v num">{fmtCost(avg)}</div></div>
      </div>

      <section className="cc-card">
        <div className="cc-head"><h2>{Icon.coin({})} {tt("spend_7d")}</h2><span className="cc-sub num">{fmtCost(data.reduce((s, v) => s + v, 0))}</span></div>
        <AreaChart data={data} labels={labels} color="var(--accent)" />
      </section>

      <div className="cost-grid">
        <section className="cc-card">
          <div className="cc-head"><h2>{Icon.folder({})} {tt("by_project")}</h2></div>
          <div className="cc-bars">
            {projects.map((p) => (
              <div className="cc-bar" key={p.repo}>
                <span className="cc-glyph" style={{ background: PHUE[p.repo] || "var(--accent)" }}>{PMETA[p.repo] || p.repo.slice(-2).toUpperCase()}</span>
                <span className="cc-bar-name num">{p.repo}</span>
                <span className="cc-bar-track"><i style={{ width: (p.cost / projMax * 100) + "%", background: PHUE[p.repo] || "var(--accent)" }}></i></span>
                <span className="cc-bar-val num">{fmtCost(p.cost)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="cc-card">
          <div className="cc-head"><h2>{Icon.pulse({})} {tt("top_agents")}</h2></div>
          <div className="cc-bars">
            {top.map((a) => (
              <div className="cc-bar" key={a.id}>
                <span className="cc-rbot" style={{ color: STATUS[a.status].clr }}><Robot role={a.role} color={STATUS[a.status].clr} size={22} /></span>
                <span className="cc-bar-name num">{a.name}</span>
                <span className="cc-bar-track"><i style={{ width: (a.cost / topMax * 100) + "%", background: STATUS[a.status].clr }}></i></span>
                <span className="cc-bar-val num">{fmtCost(a.cost)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="cc-card cc-budget">
        <div className="cc-head"><h2>{Icon.gauge({})} {tt("budget")}</h2><span className="cc-sub num">{fmtCost(used)} / {fmtCost(budget)} · {100 - usedPct}{tt("remaining")}</span></div>
        <div className="cc-budget-bar"><i style={{ width: usedPct + "%" }}></i><span className="cc-budget-lbl num">{usedPct}{tt("used")}</span></div>
      </section>
    </div>
  );
}
