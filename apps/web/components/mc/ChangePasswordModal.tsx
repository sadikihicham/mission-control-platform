"use client";

// ChangePasswordModal — modale self-service (n'importe quel rôle connecté) pour changer
// son propre mot de passe. Suit le pattern open/onClose de TweaksPanel et le style de
// formulaire de Login.tsx (auth-field / auth-err / auth-info), overlay via .modal-bg/.modal.

import { useState } from "react";
import { changePassword } from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { useI18n } from "@/lib/i18n";

export function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [err, setErr] = useState<{ current?: string; next?: string; server?: string }>({});
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const close = () => {
    setCurrent(""); setNext(""); setErr({}); setInfo(null); setBusy(false);
    onClose();
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const er: typeof err = {};
    if (!current) er.current = t("au_change_current");
    if (next.length < 6) er.next = t("au_err_newpass");
    setErr(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    try {
      await changePassword(current, next);
      setInfo(t("au_change_ok"));
      setCurrent(""); setNext(""); setErr({});
    } catch (ex) {
      setErr({ server: (ex as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-bg" onClick={close}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("au_change_title")} onClick={(e) => e.stopPropagation()}>
        <form onSubmit={submit}>
          <div className="mh">
            <div style={{ flex: 1 }}>
              <h2>{t("au_change_title")}</h2>
              <p className="who">{t("au_change_sub")}</p>
            </div>
            <button type="button" className="btn ghost icon" onClick={close} aria-label={t("close")}>
              {Icon.x({})}
            </button>
          </div>
          <div className="mb">
            {info && <div className="auth-info">{Icon.check({})}<span>{info}</span></div>}
            <div className="auth-field">
              <label htmlFor="cp-current">{t("au_change_current")}</label>
              <input
                id="cp-current"
                type="password"
                value={current}
                className={err.current ? "bad" : ""}
                placeholder={t("au_change_current_ph")}
                autoFocus
                onChange={(e) => setCurrent(e.target.value)}
              />
              {err.current && <span className="auth-err">{err.current}</span>}
            </div>
            <div className="auth-field">
              <label htmlFor="cp-next">{t("au_change_new")}</label>
              <input
                id="cp-next"
                type="password"
                value={next}
                className={err.next ? "bad" : ""}
                placeholder={t("au_change_new_ph")}
                onChange={(e) => setNext(e.target.value)}
              />
              {err.next && <span className="auth-err">{err.next}</span>}
            </div>
            {err.server && <span className="auth-err" style={{ display: "block", marginTop: 8 }}>{err.server}</span>}
          </div>
          <div className="mf">
            <button type="button" className="btn ghost grow" onClick={close}>{t("np_cancel")}</button>
            <button type="submit" className="btn primary grow" disabled={busy}>
              {Icon.check({})} {busy ? "…" : t("au_change_btn")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
