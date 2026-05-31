"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "fr" | "en" | "ar";

const STR: Record<Lang, Record<string, string>> = {
  fr: {
    nav_fleet: "Flotte", nav_projects: "Projets", nav_overview: "Vue d'ensemble", nav_hierarchy: "Hiérarchie", nav_audit: "Audit",
    new_project: "Nouveau projet", mini_active: "Actifs", mini_blocked: "Bloqués", mini_waiting: "En attente", logout: "Déconnexion",
    search_ph: "Rechercher un projet, un agent…", live: "live", polling: "polling",
    sum_projects: "Projets", sum_active: "Actifs", sum_review: "À revoir", sum_tasks: "Tâches", global_progress: "Avancement global",
    u_agents: "agents", u_tasks: "tâches", open: "Ouvrir", to_review: "à revoir", status_lbl: "Statut", del: "Supprimer",
    no_plan: "Pas de plan détaillé", no_agent: "Aucun agent sur ce projet.", agents_sec: "Agents", hint_active: "actifs",
    st_active: "Actifs", st_blocked: "Bloqués", st_stale: "Inactifs", st_queue: "En file", st_done: "Terminés", none_here: "Aucun agent ici.",
    f_all: "Tous", f_working: "Actifs", f_blocked: "Bloqués", f_stale: "Inactifs", f_idle: "En file", f_done: "Terminés",
    cmd_ph: "Rechercher projet, agent, action…", cmd_none: "Aucun résultat", cmd_move: "naviguer", cmd_open: "ouvrir",
    grp_nav: "Navigation", grp_actions: "Actions", grp_projects: "Projets", grp_fleet: "Flotte",
    a_new: "Nouveau projet", a_theme: "Basculer le thème", a_logout: "Déconnexion",
    tw_title: "Tweaks", tw_ambiances: "Ambiances", tw_theme: "Thème", tw_dark: "Mode sombre", tw_accent: "Accent",
    tw_display: "Affichage", tw_density: "Densité", tw_radius: "Arrondi", tw_shadow: "Ombres",
    tw_aurora_glow: "Aurora & glow", tw_aurora: "Aurora", tw_speed: "Vitesse", tw_glow: "Glow agents",
    np_name: "Nom du projet", np_desc: "Description (optionnel)", np_create: "Créer", np_creating: "Création…", np_cancel: "Annuler",
    d_activity: "Activité", d_progress: "Progression", d_noact: "Aucune activité enregistrée.",
    v_progress: "Progression", v_tasks: "Tâches", v_beat: "Dernier signal", v_state: "État", v_blocker: "Blocage",
    au_tagline: "Supervisez votre flotte d'agents IA en temps réel.",
    au_p1: "Projets, flotte et hiérarchie en un coup d'œil", au_p2: "Détection des agents bloqués et inactifs", au_p3: "Temps réel WebSocket · multilingue · thèmes",
    au_login_title: "Connexion", au_login_sub: "Accédez à votre cockpit de supervision.",
    au_email: "Email", au_password: "Mot de passe", au_email_ph: "vous@exemple.com", au_pass_ph: "••••••••",
    au_remember: "Se souvenir de moi", au_forgot: "Mot de passe oublié ?", au_signin: "Se connecter",
    au_err_email: "Adresse email invalide.", au_err_pass: "6 caractères minimum.",
    git_section: "Dépôt Git", git_repo: "Dépôt GitHub (owner/nom)", git_none: "Aucun dépôt lié.", git_unavail: "Dépôt indisponible.",
    git_commits: "Derniers commits", git_prs: "Pull requests ouvertes", git_branches_n: "branches", git_issues: "issues",
    lang: "Langue",
  },
  en: {
    nav_fleet: "Fleet", nav_projects: "Projects", nav_overview: "Overview", nav_hierarchy: "Hierarchy", nav_audit: "Audit",
    new_project: "New project", mini_active: "Active", mini_blocked: "Blocked", mini_waiting: "Queued", logout: "Sign out",
    search_ph: "Search a project, an agent…", live: "live", polling: "polling",
    sum_projects: "Projects", sum_active: "Active", sum_review: "Review", sum_tasks: "Tasks", global_progress: "Global progress",
    u_agents: "agents", u_tasks: "tasks", open: "Open", to_review: "to review", status_lbl: "Status", del: "Delete",
    no_plan: "No detailed plan", no_agent: "No agent on this project.", agents_sec: "Agents", hint_active: "active",
    st_active: "Active", st_blocked: "Blocked", st_stale: "Stale", st_queue: "Queued", st_done: "Done", none_here: "No agent here.",
    f_all: "All", f_working: "Active", f_blocked: "Blocked", f_stale: "Stale", f_idle: "Queued", f_done: "Done",
    cmd_ph: "Search project, agent, action…", cmd_none: "No result", cmd_move: "navigate", cmd_open: "open",
    grp_nav: "Navigation", grp_actions: "Actions", grp_projects: "Projects", grp_fleet: "Fleet",
    a_new: "New project", a_theme: "Toggle theme", a_logout: "Sign out",
    tw_title: "Tweaks", tw_ambiances: "Presets", tw_theme: "Theme", tw_dark: "Dark mode", tw_accent: "Accent",
    tw_display: "Display", tw_density: "Density", tw_radius: "Radius", tw_shadow: "Shadows",
    tw_aurora_glow: "Aurora & glow", tw_aurora: "Aurora", tw_speed: "Speed", tw_glow: "Agent glow",
    np_name: "Project name", np_desc: "Description (optional)", np_create: "Create", np_creating: "Creating…", np_cancel: "Cancel",
    d_activity: "Activity", d_progress: "Progress", d_noact: "No activity recorded.",
    v_progress: "Progress", v_tasks: "Tasks", v_beat: "Last heartbeat", v_state: "State", v_blocker: "Blocker",
    au_tagline: "Monitor your AI agent fleet in real time.",
    au_p1: "Projects, fleet and hierarchy at a glance", au_p2: "Blocked & stale agent detection", au_p3: "Real-time over WebSocket · multilingual · themes",
    au_login_title: "Sign in", au_login_sub: "Access your supervision cockpit.",
    au_email: "Email", au_password: "Password", au_email_ph: "you@example.com", au_pass_ph: "••••••••",
    au_remember: "Remember me", au_forgot: "Forgot password?", au_signin: "Sign in",
    au_err_email: "Invalid email address.", au_err_pass: "6 characters minimum.",
    git_section: "Git repository", git_repo: "GitHub repo (owner/name)", git_none: "No repository linked.", git_unavail: "Repository unavailable.",
    git_commits: "Latest commits", git_prs: "Open pull requests", git_branches_n: "branches", git_issues: "issues",
    lang: "Language",
  },
  ar: {
    nav_fleet: "الأسطول", nav_projects: "المشاريع", nav_overview: "نظرة عامة", nav_hierarchy: "التسلسل", nav_audit: "تدقيق",
    new_project: "مشروع جديد", mini_active: "نشِط", mini_blocked: "محظور", mini_waiting: "بالانتظار", logout: "تسجيل الخروج",
    search_ph: "ابحث عن مشروع أو وكيل…", live: "مباشر", polling: "استطلاع",
    sum_projects: "المشاريع", sum_active: "نشِط", sum_review: "للمراجعة", sum_tasks: "المهام", global_progress: "التقدم العام",
    u_agents: "وكلاء", u_tasks: "مهام", open: "فتح", to_review: "للمراجعة", status_lbl: "الحالة", del: "حذف",
    no_plan: "لا خطة مفصلة", no_agent: "لا يوجد وكيل على هذا المشروع.", agents_sec: "الوكلاء", hint_active: "نشِط",
    st_active: "نشِط", st_blocked: "محظور", st_stale: "خامل", st_queue: "بالانتظار", st_done: "منجز", none_here: "لا وكيل هنا.",
    f_all: "الكل", f_working: "نشِط", f_blocked: "محظور", f_stale: "خامل", f_idle: "بالانتظار", f_done: "منجز",
    cmd_ph: "ابحث عن مشروع أو وكيل أو إجراء…", cmd_none: "لا نتيجة", cmd_move: "تنقّل", cmd_open: "فتح",
    grp_nav: "التنقل", grp_actions: "إجراءات", grp_projects: "المشاريع", grp_fleet: "الأسطول",
    a_new: "مشروع جديد", a_theme: "تبديل السمة", a_logout: "تسجيل الخروج",
    tw_title: "إعدادات", tw_ambiances: "أنماط", tw_theme: "السمة", tw_dark: "الوضع الداكن", tw_accent: "اللون",
    tw_display: "العرض", tw_density: "الكثافة", tw_radius: "الاستدارة", tw_shadow: "الظلال",
    tw_aurora_glow: "الأورورا والتوهّج", tw_aurora: "الأورورا", tw_speed: "السرعة", tw_glow: "توهّج الوكلاء",
    np_name: "اسم المشروع", np_desc: "وصف (اختياري)", np_create: "إنشاء", np_creating: "جارٍ الإنشاء…", np_cancel: "إلغاء",
    d_activity: "النشاط", d_progress: "التقدّم", d_noact: "لا نشاط مسجّل.",
    v_progress: "التقدّم", v_tasks: "المهام", v_beat: "آخر إشارة", v_state: "الحالة", v_blocker: "العائق",
    au_tagline: "راقب أسطول وكلائك بالذكاء الاصطناعي في الوقت الفعلي.",
    au_p1: "المشاريع والأسطول والتسلسل بلمحة", au_p2: "كشف الوكلاء المحظورين والخاملين", au_p3: "زمن حقيقي عبر WebSocket · متعدد اللغات · سمات",
    au_login_title: "تسجيل الدخول", au_login_sub: "ادخل إلى لوحة الإشراف.",
    au_email: "البريد الإلكتروني", au_password: "كلمة المرور", au_email_ph: "you@example.com", au_pass_ph: "••••••••",
    au_remember: "تذكّرني", au_forgot: "نسيت كلمة المرور؟", au_signin: "تسجيل الدخول",
    au_err_email: "بريد إلكتروني غير صالح.", au_err_pass: "6 أحرف على الأقل.",
    git_section: "مستودع Git", git_repo: "مستودع GitHub (owner/name)", git_none: "لا مستودع مرتبط.", git_unavail: "المستودع غير متاح.",
    git_commits: "آخر الالتزامات", git_prs: "طلبات السحب المفتوحة", git_branches_n: "فروع", git_issues: "مشاكل",
    lang: "اللغة",
  },
};

type I18n = { lang: Lang; t: (k: string) => string; setLang: (l: Lang) => void };
const Ctx = createContext<I18n>({ lang: "fr", t: (k) => k, setLang: () => {} });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("fr");
  useEffect(() => {
    const s = localStorage.getItem("mc-lang") as Lang | null;
    if (s && STR[s]) setLangState(s);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("mc-lang", lang);
  }, [lang]);
  const t = useCallback((k: string) => STR[lang][k] ?? STR.fr[k] ?? k, [lang]);
  return <Ctx.Provider value={{ lang, t, setLang: setLangState }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
