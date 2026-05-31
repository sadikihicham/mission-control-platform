"use client";

import { useState } from "react";
import { login } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { useI18n, type Lang } from "@/lib/i18n";

const LANGS: { id: Lang; short: string }[] = [
  { id: "fr", short: "FR" },
  { id: "en", short: "EN" },
  { id: "ar", short: "ع" },
];

export function Login({
  onLogin,
  theme,
  onToggleTheme,
}: {
  onLogin: (token: string) => void;
  theme?: "dark" | "light";
  onToggleTheme?: () => void;
}) {
  const { t, lang, setLang } = useI18n();
  const [email, setEmail] = useState("admin@mc.local");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<{ email?: string; password?: string; server?: string }>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const er: typeof err = {};
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) er.email = t("au_err_email");
    if (!password) er.password = t("au_err_pass");
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    try {
      const token = await login(email, password);
      onLogin(token);
    } catch (ex) {
      setErr({ server: (ex as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <aside className="auth-aside">
        <div className="auth-brand">
          <img className="auth-logo-full" src="/brand-logo.png" alt="Mission Control" />
        </div>
        <div className="auth-pitch">
          <h1>{t("au_tagline")}</h1>
          <ul className="auth-points">
            {["au_p1", "au_p2", "au_p3"].map((k) => (
              <li key={k}><span className="ck">{Icon.check({})}</span>{t(k)}</li>
            ))}
          </ul>
        </div>
        <div className="auth-deco" aria-hidden="true">
          <span className="d d1" /><span className="d d2" /><span className="d d3" />
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-topbar">
          <div className="lang-switch">
            {LANGS.map((l) => (
              <button key={l.id} type="button" className={"ls" + (lang === l.id ? " on" : "")} onClick={() => setLang(l.id)}>{l.short}</button>
            ))}
          </div>
          {onToggleTheme && (
            <button className="btn ghost icon theme-btn" onClick={onToggleTheme} title={t("a_theme")}>
              {theme === "dark" ? Icon.sun({}) : Icon.moon({})}
            </button>
          )}
        </div>

        <form className="auth-card" onSubmit={submit}>
          <div className="auth-mobilebrand">
            <div className="logo brand-img"><img src="/brand-mark.png" alt="" /></div>
            <span>Mission Control</span>
          </div>

          <h2>{t("au_login_title")}</h2>
          <p className="auth-sub">{t("au_login_sub")}</p>

          <div className="auth-field">
            <label htmlFor="email">{t("au_email")}</label>
            <input id="email" type="email" value={email} className={err.email ? "bad" : ""} placeholder={t("au_email_ph")} onChange={(e) => setEmail(e.target.value)} />
            {err.email && <span className="auth-err">{err.email}</span>}
          </div>
          <div className="auth-field">
            <label htmlFor="password">{t("au_password")}</label>
            <input id="password" type="password" value={password} className={err.password ? "bad" : ""} placeholder={t("au_pass_ph")} autoFocus onChange={(e) => setPassword(e.target.value)} />
            {err.password && <span className="auth-err">{err.password}</span>}
          </div>

          <div className="auth-row">
            <label className="auth-check"><input type="checkbox" defaultChecked /><span>{t("au_remember")}</span></label>
            <a className="auth-link" href="#" onClick={(e) => e.preventDefault()}>{t("au_forgot")}</a>
          </div>

          {err.server && <span className="auth-err" style={{ display: "block", marginBottom: 8 }}>{err.server}</span>}

          <button className="btn primary auth-submit" type="submit" disabled={busy}>
            {Icon.logout({})} {busy ? "…" : t("au_signin")}
          </button>
        </form>
      </main>
    </div>
  );
}
