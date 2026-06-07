"use client";

import { useState } from "react";
import { login, forgotPassword, resetPassword } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { useI18n, type Lang } from "@/lib/i18n";

const LANGS: { id: Lang; short: string }[] = [
  { id: "fr", short: "FR" },
  { id: "en", short: "EN" },
  { id: "ar", short: "ع" },
];

type Mode = "login" | "forgot" | "reset";

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
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("demo@infinity.ae");
  const [password, setPassword] = useState("password");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [err, setErr] = useState<{ email?: string; password?: string; token?: string; newPassword?: string; server?: string }>({});
  const [info, setInfo] = useState<string | null>(null);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reset = (m: Mode) => { setErr({}); setInfo(null); setDevToken(null); setMode(m); };
  const emailOk = (v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);

  async function submitLogin(e: React.FormEvent) {
    e.preventDefault();
    const er: typeof err = {};
    if (!emailOk(email)) er.email = t("au_err_email");
    if (!password) er.password = t("au_err_pass");
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    try {
      const tok = await login(email, password);
      onLogin(tok);
    } catch (ex) {
      setErr({ server: (ex as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function submitForgot(e: React.FormEvent) {
    e.preventDefault();
    if (!emailOk(email)) { setErr({ email: t("au_err_email") }); return; }
    setErr({}); setBusy(true);
    try {
      const res = await forgotPassword(email);
      setInfo(t("au_sent"));
      setDevToken(res.dev_token ?? null);
    } catch (ex) {
      setErr({ server: (ex as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function submitReset(e: React.FormEvent) {
    e.preventDefault();
    const er: typeof err = {};
    if (!token.trim()) er.token = t("au_token");
    if (newPassword.length < 6) er.newPassword = t("au_err_newpass");
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    try {
      await resetPassword(token.trim(), newPassword);
      reset("login");
      setInfo(t("au_reset_ok"));
      setPassword("");
    } catch (ex) {
      setErr({ server: (ex as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const title = mode === "login" ? t("au_login_title") : mode === "forgot" ? t("au_forgot_title") : t("au_reset_title");
  const sub = mode === "login" ? t("au_login_sub") : mode === "forgot" ? t("au_forgot_sub") : t("au_reset_sub");

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

        <form className="auth-card" onSubmit={mode === "login" ? submitLogin : mode === "forgot" ? submitForgot : submitReset}>
          <div className="auth-mobilebrand">
            <div className="logo brand-img"><img src="/brand-mark.png" alt="" /></div>
            <span>Mission Control</span>
          </div>

          <h2>{title}</h2>
          <p className="auth-sub">{sub}</p>

          {info && <div className="auth-info">{Icon.check({})}<span>{info}</span></div>}

          {/* ---- Connexion ---- */}
          {mode === "login" && (
            <>
              <div className="auth-field">
                <label htmlFor="email">{t("au_email")}</label>
                <input id="email" type="email" value={email} className={err.email ? "bad" : ""} placeholder={t("au_email_ph")} onChange={(e) => setEmail(e.target.value)} />
                {err.email && <span className="auth-err">{err.email}</span>}
              </div>
              <div className="auth-field">
                <label htmlFor="password">{t("au_password")}</label>
                <input id="password" type="password" value={password} className={err.password ? "bad" : ""} placeholder={t("au_pass_ph")} onChange={(e) => setPassword(e.target.value)} />
                {err.password && <span className="auth-err">{err.password}</span>}
              </div>
              <div className="auth-row">
                <label className="auth-check"><input type="checkbox" defaultChecked /><span>{t("au_remember")}</span></label>
                <a className="auth-link" href="#" onClick={(e) => { e.preventDefault(); reset("forgot"); }}>{t("au_forgot")}</a>
              </div>
              {err.server && <span className="auth-err" style={{ display: "block", marginBottom: 8 }}>{err.server}</span>}
              <button className="btn primary auth-submit" type="submit" disabled={busy}>
                {Icon.logout({})} {busy ? "…" : t("au_signin")}
              </button>
            </>
          )}

          {/* ---- Mot de passe oublié ---- */}
          {mode === "forgot" && (
            <>
              <div className="auth-field">
                <label htmlFor="email-f">{t("au_email")}</label>
                <input id="email-f" type="email" value={email} className={err.email ? "bad" : ""} placeholder={t("au_email_ph")} autoFocus onChange={(e) => setEmail(e.target.value)} />
                {err.email && <span className="auth-err">{err.email}</span>}
              </div>
              {devToken && (
                <div className="auth-devtoken">
                  <span className="auth-devtoken-lbl">{t("au_dev_token")}</span>
                  <code>{devToken}</code>
                  <button type="button" className="btn sm" onClick={() => { setToken(devToken); reset("reset"); }}>{t("au_use_token")}</button>
                </div>
              )}
              {err.server && <span className="auth-err" style={{ display: "block", marginBottom: 8 }}>{err.server}</span>}
              {!devToken && (
                <button className="btn primary auth-submit" type="submit" disabled={busy}>
                  {Icon.bell({})} {busy ? "…" : t("au_forgot_send")}
                </button>
              )}
              <a className="auth-link auth-back" href="#" onClick={(e) => { e.preventDefault(); reset("login"); }}>{t("au_back_login")}</a>
            </>
          )}

          {/* ---- Réinitialisation ---- */}
          {mode === "reset" && (
            <>
              <div className="auth-field">
                <label htmlFor="token">{t("au_token")}</label>
                <input id="token" type="text" value={token} className={err.token ? "bad" : ""} placeholder={t("au_token_ph")} autoFocus onChange={(e) => setToken(e.target.value)} />
                {err.token && <span className="auth-err">{err.token}</span>}
              </div>
              <div className="auth-field">
                <label htmlFor="newpass">{t("au_newpass")}</label>
                <input id="newpass" type="password" value={newPassword} className={err.newPassword ? "bad" : ""} placeholder={t("au_newpass_ph")} onChange={(e) => setNewPassword(e.target.value)} />
                {err.newPassword && <span className="auth-err">{err.newPassword}</span>}
              </div>
              {err.server && <span className="auth-err" style={{ display: "block", marginBottom: 8 }}>{err.server}</span>}
              <button className="btn primary auth-submit" type="submit" disabled={busy}>
                {Icon.check({})} {busy ? "…" : t("au_reset_btn")}
              </button>
              <a className="auth-link auth-back" href="#" onClick={(e) => { e.preventDefault(); reset("login"); }}>{t("au_back_login")}</a>
            </>
          )}
        </form>
      </main>
    </div>
  );
}
