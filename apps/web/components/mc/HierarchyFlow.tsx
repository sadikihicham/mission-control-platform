// @ts-nocheck
"use client";

// HierarchyFlow.tsx — vue hiérarchie/flux LIVE.
// Arbre top-down repliable : orchestrateur → projets → agents → tâches.
// Reconstruit dynamiquement depuis l'API (getProjects → getProject) dans un effet.
// Layout calculé analytiquement (aucune mesure DOM). Les métriques non suivies
// côté serveur (coût/tokens/modèle/flux inter-agents) sont dégradées proprement.

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Icon } from "@/components/mc/icons";
import { Ant } from "@/components/mc/Ant";
import { Robot, robotRoleLabel, robotActivityOf } from "@/components/mc/Robot";
import { getProjects, getProject } from "@/lib/api";
import { bucketOf, fmtAge } from "@/lib/mc";
import { useI18n } from "@/lib/i18n";

const HI = Icon;

// shared module-level translation table for this view
const TR = {
  fr: {
    agent: "Agent", task: "Tâche", workflow: "Workflow", active: "actifs", blocked: "bloqués",
    flow: "Flux", expand_all: "Tout déplier", collapse_all: "Tout replier",
    collapse: "Replier", expand: "Déplier", reset_pos: "Réinitialiser",
    recommendation: "Recommandation", decision: "Décision", applied: "Appliqué",
    sol_blocked: "Pré-analyser le diff : approuver automatiquement si faible risque, sinon escalader vers un humain.",
    sol_active: "Laisser l'agent terminer ; surveiller la durée et la consommation de tokens.",
    sol_todo: "Prioriser si sans dépendance, sinon planifier après l'étape bloquante.",
    sol_done: "Étape terminée — vérifier le résultat avant la suivante.",
    sol_default: "—",
    sl_blocked: "Bloquée", sl_active: "Active", sl_done: "Réussie", sl_todo: "En file",
    dec_unblock: "Débloquer", dec_reassign: "Réassigner", dec_inspect: "Inspecter",
    dec_continue: "Continuer", dec_pause: "Mettre en pause", dec_prioritize: "Prioriser",
    agents: "agents", fleet: "Flotte", projects: "projets", tasks: "tâches",
    loading: "Chargement de la hiérarchie…",
    empty: "Aucun projet ni agent à afficher pour le moment.",
    flow_off: "Flux inter-agents indisponible (non suivi côté serveur).",
  },
  en: {
    agent: "Agent", task: "Task", workflow: "Workflow", active: "active", blocked: "blocked",
    flow: "Flow", expand_all: "Expand all", collapse_all: "Collapse all",
    collapse: "Collapse", expand: "Expand", reset_pos: "Reset layout",
    recommendation: "Recommendation", decision: "Decision", applied: "Applied",
    sol_blocked: "Pre-analyze the diff: auto-approve if low-risk, otherwise escalate to a human.",
    sol_active: "Let the agent finish; monitor duration and token usage.",
    sol_todo: "Prioritize if dependency-free, otherwise schedule after the blocking step.",
    sol_done: "Step complete — verify the output before the next one.",
    sol_default: "—",
    sl_blocked: "Blocked", sl_active: "Active", sl_done: "Passed", sl_todo: "Queued",
    dec_unblock: "Unblock", dec_reassign: "Reassign", dec_inspect: "Inspect",
    dec_continue: "Continue", dec_pause: "Pause", dec_prioritize: "Prioritize",
    agents: "agents", fleet: "Fleet", projects: "projects", tasks: "tasks",
    loading: "Loading hierarchy…",
    empty: "No project or agent to display yet.",
    flow_off: "Inter-agent flow unavailable (not tracked server-side).",
  },
  ar: {
    agent: "وكيل", task: "مهمة", workflow: "سير العمل", active: "نشِط", blocked: "محظور",
    flow: "التدفق", expand_all: "توسيع الكل", collapse_all: "طي الكل",
    collapse: "طي", expand: "توسيع", reset_pos: "إعادة الضبط",
    recommendation: "توصية", decision: "قرار", applied: "تم التطبيق",
    sol_blocked: "حلّل الفرق مسبقًا: وافق تلقائيًا إذا كانت المخاطر منخفضة، وإلا فصعّد إلى إنسان.",
    sol_active: "اترك الوكيل ينهي عمله؛ راقب المدة واستهلاك الرموز.",
    sol_todo: "أعطِ الأولوية إن لم تكن هناك تبعية، وإلا فجدول بعد الخطوة المعيقة.",
    sol_done: "اكتملت الخطوة — تحقق من النتيجة قبل الانتقال إلى التالية.",
    sol_default: "—",
    sl_blocked: "محظورة", sl_active: "نشطة", sl_done: "ناجحة", sl_todo: "في الطابور",
    dec_unblock: "إلغاء الحظر", dec_reassign: "إعادة التعيين", dec_inspect: "فحص",
    dec_continue: "متابعة", dec_pause: "إيقاف مؤقت", dec_prioritize: "إعطاء الأولوية",
    agents: "وكلاء", fleet: "الأسطول", projects: "مشاريع", tasks: "مهام",
    loading: "جارٍ تحميل الهيكل…",
    empty: "لا يوجد مشروع أو وكيل للعرض بعد.",
    flow_off: "تدفق الوكلاء غير متاح (غير متتبَّع على الخادم).",
  },
};

// node geometry per type
const DIM = {
  orchestrator: { w: 230, h: 76 },
  lead: { w: 208, h: 66 },
  worker: { w: 210, h: 70 },
  task: { w: 176, h: 42 },
};
const COL = 56; // horizontal gap between leaf slots
const ROW = 132; // vertical gap between depth levels

const STCLR = { running: "var(--run)", waiting: "var(--wait)", blocked: "var(--block)", done: "var(--done)" };

// Mappe l'état live d'un agent (idle|working|blocked|done|error|stale) vers
// les 4 familles d'affichage du design (running|waiting|blocked|done).
function liveStatus(state) {
  return bucketOf(state || "idle");
}

// Mappe l'état live d'une tâche vers les 4 états de carte de tâche (done|active|blocked|todo).
function liveTaskState(state) {
  const b = bucketOf(state || "idle");
  if (b === "done") return "done";
  if (b === "blocked") return "blocked";
  if (b === "running") return "active";
  return "todo";
}

// Reconstruit l'arbre unifié à partir des projets/tâches/agents LIVE.
// Structure : orchestrateur (flotte) → projet (lead) → agent (worker) → tâche.
function buildLiveTree(projects, details, tt) {
  const projNodes = projects.map((p) => {
    const det = details[p.id];
    // Agents live du projet (depuis le détail si dispo, sinon vide).
    const detAgents = (det && det.agents) || [];
    // Index tâche→agents : depuis les tâches du détail, on associe agents et sous-tâches.
    const tasks = (det && det.tasks) || [];

    // Carte clé agent → liste de tâches (cartes feuilles) où il intervient.
    const tasksByAgent = {};
    tasks.forEach((tk) => {
      const involved = new Set();
      (tk.agents || []).forEach((a) => involved.add(a.agent));
      (tk.subtasks || []).forEach((s) => { if (s.agent) involved.add(s.agent); });
      involved.forEach((key) => {
        (tasksByAgent[key] = tasksByAgent[key] || []).push(tk);
      });
    });

    const agentNodes = detAgents.map((a) => {
      const myTasks = tasksByAgent[a.agent] || [];
      const taskCards = myTasks.map((tk, i) => ({
        id: p.id + "::" + a.agent + "::t" + i,
        type: "task", aid: a.agent,
        label: tk.title,
        state: liveTaskState(tk.state),
        agentRef: a,
      }));
      // Repli : si aucune tâche associée, on dérive une carte unique depuis la tâche courante de l'agent.
      if (taskCards.length === 0 && a.task) {
        taskCards.push({
          id: p.id + "::" + a.agent + "::t0",
          type: "task", aid: a.agent,
          label: a.task,
          state: liveTaskState(a.state),
          agentRef: a,
        });
      }
      return {
        id: p.id + "::" + a.agent,
        type: "agent", role: "worker",
        name: a.label || a.agent,
        agent: a,
        status: liveStatus(a.state),
        progress: a.progress || 0,
        repo: a.module || a.branch || "—",
        kids: taskCards,
      };
    });

    // Statut agrégé du projet depuis ses compteurs/agents.
    const anyBlocked = agentNodes.some((n) => n.status === "blocked") || (p.agents_blocked || 0) > 0;
    const anyRun = agentNodes.some((n) => n.status === "running") || (p.agents_active || 0) > 0;
    const status = anyBlocked ? "blocked" : anyRun ? "running" : p.status === "done" ? "done" : "running";

    return {
      id: p.id,
      type: "agent", role: "lead",
      name: p.name,
      status,
      progress: p.progress || 0,
      count: p.agents_total ?? agentNodes.length,
      note: (p.tasks_done ?? 0) + "/" + (p.tasks_total ?? 0) + " " + tt("tasks"),
      kids: agentNodes,
    };
  });

  const totalAgents = projects.reduce((s, p) => s + (p.agents_total || 0), 0);
  const anyBlocked = projNodes.some((n) => n.status === "blocked");
  const anyRun = projNodes.some((n) => n.status === "running");

  return {
    id: "__fleet__",
    type: "agent", role: "orchestrator",
    name: tt("fleet"),
    status: anyBlocked ? "blocked" : anyRun ? "running" : "done",
    progress: projects.length
      ? Math.round(projects.reduce((s, p) => s + (p.progress || 0), 0) / projects.length)
      : 0,
    note: projects.length + " " + tt("projects") + " · " + totalAgents + " " + tt("agents"),
    kids: projNodes,
  };
}

// assign x/y positions respecting collapsed set
function layout(root, collapsed) {
  const nodes = []; const links = []; let leaf = 0;
  function place(n, depth) {
    const dim = DIM[n.role === "worker" || n.type === "task" ? (n.type === "task" ? "task" : "worker") : n.role] || DIM.worker;
    const open = n.kids && n.kids.length && !collapsed.has(n.id);
    let x;
    if (!open) {
      x = leaf * (DIM.task.w + COL) + dim.w / 2; leaf++;
    } else {
      const xs = n.kids.map((k) => place(k, depth + 1));
      x = (xs[0] + xs[xs.length - 1]) / 2;
    }
    const y = depth * ROW;
    nodes.push({ ...n, x, y, w: dim.w, h: dim.h, depth, open, hasKids: !!(n.kids && n.kids.length) });
    if (open) n.kids.forEach((k) => links.push({ from: n.id, to: k.id }));
    return x;
  }
  place(root, 0);
  const byId = {}; nodes.forEach((n) => (byId[n.id] = n));
  const W = leaf * (DIM.task.w + COL) + 80;
  const H = (Math.max(...nodes.map((n) => n.depth)) + 1) * ROW + 90;
  return { nodes, links, byId, W, H };
}

function vpath(a, b) { // parent bottom -> child top (cubic S)
  const x1 = a.x, y1 = a.y + a.h, x2 = b.x, y2 = b.y, my = (y1 + y2) / 2;
  return `M${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
}

// hook de drag partagé : déplacement à la souris via pointer events, distingue clic vs glisser.
function useNodeDrag(id, zoom, onDrag) {
  const drag = useRef(null);
  const moved = useRef(false);
  const onPointerDown = (e) => {
    if (e.button !== 0) return; // bouton gauche uniquement
    if (e.target.closest && e.target.closest(".h-toggle")) return; // ne pas capturer sur le bouton replier/déplier
    drag.current = { lastX: e.clientX, lastY: e.clientY, totX: 0, totY: 0 };
    moved.current = false;
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch {}
  };
  const onPointerMove = (e) => {
    const d = drag.current; if (!d) return;
    const ddx = e.clientX - d.lastX, ddy = e.clientY - d.lastY;
    d.lastX = e.clientX; d.lastY = e.clientY; d.totX += ddx; d.totY += ddy;
    if (Math.abs(d.totX) > 3 || Math.abs(d.totY) > 3) moved.current = true;
    onDrag(id, ddx / zoom, ddy / zoom); // compense le zoom du canvas
  };
  const onPointerUp = (e) => {
    drag.current = null;
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch {}
  };
  // si un déplacement vient d'avoir lieu, on neutralise le clic d'ouverture qui suit
  const guardClick = (fn) => () => { if (moved.current) { moved.current = false; return; } fn && fn(); };
  return { onPointerDown, onPointerMove, onPointerUp, guardClick };
}

function HNode({ n, onToggle, onOpen, onTaskClick, zoom, onDrag }) {
  const { lang } = useI18n();
  const tt = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const clr = STCLR[n.status] || "var(--tx-dim)";
  const { onPointerDown, onPointerMove, onPointerUp, guardClick } = useNodeDrag(n.id, zoom, onDrag);
  const dragStyle = { cursor: "grab", touchAction: "none" };
  if (n.type === "task") {
    const TSTATE = { done: "happy", active: "working", blocked: "searching" };
    const TCLR = { done: "var(--done)", active: "var(--run)", blocked: "var(--block)" };
    const aSt = TSTATE[n.state] || "sleeping";
    const aClr = TCLR[n.state] || "var(--tx-dim)";
    return (
      <div className={"h-task clickable st-" + n.state} style={{ left: n.x - n.w / 2, top: n.y, width: n.w, height: n.h, ...dragStyle }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onClick={guardClick(() => onTaskClick && onTaskClick(n))}>
        <span className="tk-ant" style={{ color: aClr }}><Ant state={aSt} color={aClr} size={20} /></span>
        <span className="tk-label">{n.label}</span>
      </div>
    );
  }
  const isWorker = n.role === "worker";
  // Rôle d'affichage du robot : pour un agent live, on retombe sur "developer".
  const botRole = isWorker ? "developer" : n.role;
  return (
    <div
      className={"h-node " + n.role + (isWorker && n.status === "running" ? " run-anim" : "")}
      style={{ left: n.x - n.w / 2, top: n.y, width: n.w, height: n.h, "--clr": clr, ...dragStyle }}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
      onClick={guardClick(() => isWorker && n.agent && onOpen(n.agent))}
    >
      <div className="h-hex bot" style={{ color: clr }}>
        <Robot
          role={botRole}
          color={clr}
          size={n.role === "orchestrator" ? 46 : 38}
          status={isWorker ? "running" : "running"}
          paused={false}
          activity={n.agent ? robotActivityOf({ task: n.agent.task, step: n.agent.label }) : "thinking"}
        />
        <span className="h-ring"></span>
      </div>
      <div className="h-body">
        <div className="h-name">{n.name}</div>
        <div className="h-sub">
          {isWorker ? <>{robotRoleLabel("developer")} · {n.repo}{n.agent && n.agent.age_seconds != null ? " · " + fmtAge(n.agent.age_seconds) : ""}</>
            : n.role === "lead" ? <>{robotRoleLabel("lead")} · {n.count} {tt("agents")}</>
            : <>{robotRoleLabel("orchestrator")} · {n.note}</>}
        </div>
        {isWorker && n.status !== "waiting" && (
          <div className="h-prog"><i style={{ width: n.progress + "%", background: clr }}></i></div>
        )}
      </div>
      <span className="h-status" style={{ background: clr }}></span>
      {n.hasKids && (
        <button className="h-toggle" onClick={(e) => { e.stopPropagation(); onToggle(n.id); }} title={n.open ? tt("collapse") : tt("expand")}>
          {n.open ? HI.chevron({ style: { width: 13, height: 13, transform: "rotate(90deg)" } }) : <span className="h-count">{n.kids.length}</span>}
        </button>
      )}
    </div>
  );
}

function TaskModal({ n, agent, onClose, onOpen }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const [applied, setApplied] = useState(null);
  const TSTATE = { done: "happy", active: "working", blocked: "searching" };
  const TCLR = { done: "var(--done)", active: "var(--run)", blocked: "var(--block)" };
  const clr = TCLR[n.state] || "var(--tx-dim)";
  const label = n.label;
  // proposed solution per state
  const SOL = {
    blocked: { sk: "sol_blocked", conf: 88 },
    active: { sk: "sol_active", conf: 84 },
    todo: { sk: "sol_todo", conf: 79 },
    done: { sk: "sol_done", conf: 96 },
  }[n.state] || { sk: "sol_default", conf: 75 };
  const STATE_LABEL = { blocked: "sl_blocked", active: "sl_active", done: "sl_done", todo: "sl_todo" };
  const decisions = {
    blocked: [{ k: "dec_unblock", primary: true }, { k: "dec_reassign" }, { k: "dec_inspect", inspect: true }],
    active: [{ k: "dec_continue", primary: true }, { k: "dec_pause" }, { k: "dec_inspect", inspect: true }],
    todo: [{ k: "dec_prioritize", primary: true }, { k: "dec_inspect", inspect: true }],
    done: [{ k: "dec_inspect", primary: true, inspect: true }],
  }[n.state] || [{ k: "dec_inspect", primary: true, inspect: true }];
  const decide = (d) => {
    if (d.inspect && agent) { onClose(); onOpen(agent); return; }
    setApplied(d.k);
    setTimeout(onClose, 1100);
  };
  if (typeof document === "undefined") return null;
  return createPortal(
    <div className="tm-bg" onClick={onClose}>
      <div className="tm" style={{ "--tc": clr }} onClick={(e) => e.stopPropagation()} role="dialog">
        <div className="tm-head">
          <span className="tm-ant" style={{ color: clr }}><Ant state={TSTATE[n.state] || "sleeping"} color={clr} size={36} /></span>
          <div className="tm-id">
            <div className="tm-t">{label}</div>
            {agent && <div className="tm-sub">{agent.label || agent.agent} · {robotRoleLabel("developer")} · {agent.module || agent.branch || "—"}</div>}
          </div>
          <button className="btn ghost icon" onClick={onClose}>{HI.x({})}</button>
        </div>
        <div className="tm-state"><span className="tm-badge" style={{ color: clr, background: "color-mix(in oklab," + clr + " 14%, transparent)" }}>{t(STATE_LABEL[n.state] || "sl_todo")}</span></div>
        <div className="tm-reco">
          <div className="tm-reco-h"><span className="tm-reco-l">{HI.spark({})} {t("recommendation")}</span><span className="tm-conf"><span className="bar"><i style={{ width: SOL.conf + "%" }}></i></span><b className="num">{SOL.conf}%</b></span></div>
          <div className="tm-reco-d">{t(SOL.sk)}</div>
        </div>
        {applied ? (
          <div className="tm-applied">{HI.check({})}<span>{t("applied")} · {t(applied)}</span></div>
        ) : (
          <div className="tm-dec">
            <div className="tm-dec-h">{t("decision")}</div>
            <div className="tm-dec-btns">
              {decisions.map((d, i) => (
                <button key={i} className={"tm-dec-btn" + (d.primary ? " primary" : "")} onClick={() => decide(d)}>
                  {d.inspect ? HI.terminal({}) : HI.check({})} {t(d.k)}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

export function HierarchyFlow({ onOpenAgent = () => {} }) {
  const { lang } = useI18n();
  const t = (k) => (TR[lang] || TR.en)[k] ?? (TR.en[k] ?? k);
  const onOpen = onOpenAgent;

  // --- Données LIVE : projets + détails (tâches/agents) reconstruits en hiérarchie. ---
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState([]);
  const [details, setDetails] = useState({});
  // Index agent (clé) → objet agent live, pour la modale de tâche.
  const agentsByKey = useMemo(() => {
    const m = {};
    Object.values(details).forEach((d) => (d.agents || []).forEach((a) => { m[a.agent] = a; }));
    return m;
  }, [details]);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const ps = await getProjects();
        if (!on) return;
        setProjects(ps);
        // Récupère les détails de chaque projet en parallèle (tâches + agents).
        const entries = await Promise.all(
          ps.map(async (p) => {
            try { return [p.id, await getProject(p.id)]; }
            catch { return [p.id, null]; }
          })
        );
        if (!on) return;
        const map = {};
        entries.forEach(([id, det]) => { if (det) map[id] = det; });
        setDetails(map);
      } catch {
        if (on) { setProjects([]); setDetails({}); }
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => { on = false; };
  }, []);

  const [taskNode, setTaskNode] = useState(null);
  const tree = useMemo(() => buildLiveTree(projects, details, t), [projects, details, lang]);

  // Parents repliés par défaut : tous les agents (les tâches sont masquées au départ).
  const allAgentIds = useMemo(() => {
    const ids = [];
    projects.forEach((p) => {
      const det = details[p.id];
      (det && det.agents || []).forEach((a) => ids.push(p.id + "::" + a.agent));
    });
    return ids;
  }, [projects, details]);
  const projectIds = useMemo(() => projects.map((p) => p.id), [projects]);

  const [collapsed, setCollapsed] = useState(() => new Set());
  // Réinitialise le repli quand la flotte change : on masque les tâches par défaut.
  useEffect(() => { setCollapsed(new Set(allAgentIds)); }, [allAgentIds.join("|")]);

  const [zoom, setZoom] = useState(0.78);
  // NB : le flux inter-agents (EDGES) du mock n'est pas suivi côté serveur — vue dégradée
  // sans arcs de workflow ni étiquettes de flux (la légende/bouton "Flux" sont retirés).
  // décalages de position par nœud (drag à la souris), appliqués par-dessus le layout calculé
  const [offsets, setOffsets] = useState({});
  const onDrag = useCallback((id, ddx, ddy) => {
    setOffsets((p) => { const c = p[id] || { dx: 0, dy: 0 }; return { ...p, [id]: { dx: c.dx + ddx, dy: c.dy + ddy } }; });
  }, []);
  const canvasRef = useRef(null);
  useEffect(() => {
    const c = canvasRef.current;
    if (c) c.scrollLeft = Math.max(0, (c.scrollWidth - c.clientWidth) / 2);
  }, [tree]);

  const L = useMemo(() => layout(tree, collapsed), [tree, collapsed]);
  // applique les décalages de drag aux positions calculées (nœuds + index pour les liens)
  const nodes2 = useMemo(
    () => L.nodes.map((n) => { const o = offsets[n.id]; return o ? { ...n, x: n.x + o.dx, y: n.y + o.dy } : n; }),
    [L, offsets]
  );
  const byId2 = useMemo(() => { const m = {}; nodes2.forEach((n) => (m[n.id] = n)); return m; }, [nodes2]);
  const toggle = (id) => setCollapsed((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const expandAll = () => setCollapsed(new Set());
  const collapseAll = () => setCollapsed(new Set([...allAgentIds, ...projectIds]));

  const isEmpty = !loading && projects.length === 0;

  return (
    <div className="h-wrap">
      <div className="h-toolbar">
        <div className="h-legend">
          <span className="lg"><span className="lg-hex"></span>{t("agent")}</span>
          <span className="lg"><span className="lg-tag"></span>{t("task")}</span>
          <span className="lg"><span className="dot" style={{ background: "var(--run)" }}></span>{t("active")}</span>
          <span className="lg"><span className="dot" style={{ background: "var(--block)" }}></span>{t("blocked")}</span>
        </div>
        <div className="h-tools">
          <button className="chip" onClick={expandAll}>{t("expand_all")}</button>
          <button className="chip" onClick={collapseAll}>{t("collapse_all")}</button>
          {Object.keys(offsets).length > 0 && <button className="chip" onClick={() => setOffsets({})}>{t("reset_pos")}</button>}
          <div className="zoomers">
            <button className="btn ghost icon sm" onClick={() => setZoom((z) => Math.max(0.45, +(z - 0.12).toFixed(2)))}>−</button>
            <span className="zlbl num">{Math.round(zoom * 100)}%</span>
            <button className="btn ghost icon sm" onClick={() => setZoom((z) => Math.min(1.4, +(z + 0.12).toFixed(2)))}>+</button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="h-canvas" style={{ display: "grid", placeItems: "center" }}>
          <div className="muted" style={{ padding: 40, fontSize: 13 }}>{t("loading")}</div>
        </div>
      ) : isEmpty ? (
        <div className="h-canvas" style={{ display: "grid", placeItems: "center" }}>
          <div className="muted" style={{ padding: 40, fontSize: 13 }}>{t("empty")}</div>
        </div>
      ) : (
        <div className="h-canvas" ref={canvasRef}>
          <div className="h-stage" style={{ width: L.W * zoom, height: L.H * zoom }}>
            <div className="h-inner" style={{ width: L.W, height: L.H, transform: `scale(${zoom})` }}>
              <svg className="h-links" width={L.W} height={L.H} viewBox={`0 0 ${L.W} ${L.H}`}>
                {L.links.map((lk, i) => {
                  const a = byId2[lk.from], b = byId2[lk.to];
                  if (!a || !b) return null;
                  return <path key={i} d={vpath(a, b)} className="lk" />;
                })}
              </svg>
              {nodes2.map((n) => (
                <HNode key={n.id} n={n} onToggle={toggle} onOpen={onOpen} onTaskClick={setTaskNode} zoom={zoom} onDrag={onDrag} />
              ))}
            </div>
          </div>
        </div>
      )}
      {taskNode && <TaskModal n={taskNode} agent={agentsByKey[taskNode.aid]} onClose={() => setTaskNode(null)} onOpen={onOpen} />}
    </div>
  );
}
