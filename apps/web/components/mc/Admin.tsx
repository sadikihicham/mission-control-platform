"use client";

// Admin.tsx — rubrique Administration (rôle admin uniquement) : gestion des
// utilisateurs et des identifiants par agent, en 2 onglets indépendants.

import { useCallback, useEffect, useState } from "react";
import {
  ROLES,
  createUser,
  getAgents,
  getUsers,
  revokeAgentToken,
  updateUser,
  type Agent,
  type Me,
} from "@/lib/api";
import { Icon } from "@/components/mc/icons";
import { useI18n } from "@/lib/i18n";

function NewUserForm({ onCreated }: { onCreated: () => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string>("viewer");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <form
      className="np-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true); setErr(null);
        try {
          await createUser({ email, password, role });
          setEmail(""); setPassword(""); setRole("viewer");
          onCreated();
        } catch (e) {
          setErr((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="np-row">
        <input value={email} onChange={(e) => setEmail(e.target.value)} required type="email" placeholder={t("adm_email")} autoComplete="off" />
        <input value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} type="password" placeholder={t("adm_password")} autoComplete="new-password" />
        <select className="pd-select" value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((r) => (<option key={r} value={r}>{r}</option>))}
        </select>
      </div>
      {err && <div className="err">{err}</div>}
      <div className="np-row">
        <button type="submit" className="btn primary" disabled={busy}>{Icon.plus({})} {busy ? t("np_creating") : t("adm_create_user")}</button>
      </div>
    </form>
  );
}

function UserRow({ user, isSelf, onChanged }: { user: Me; isSelf: boolean; onChanged: () => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const apply = async (patch: { role?: string; is_active?: boolean }) => {
    setBusy(true); setErr(null);
    try { await updateUser(user.id, patch); onChanged(); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="adm-row">
      <div className="adm-id">
        <div className="nm">{user.full_name || user.email}</div>
        <div className="ds">{user.email}</div>
      </div>
      <select
        className="pd-select"
        value={user.role}
        disabled={busy || isSelf}
        title={isSelf ? t("adm_self_guard") : undefined}
        onChange={(e) => apply({ role: e.target.value })}
      >
        {ROLES.map((r) => (<option key={r} value={r}>{r}</option>))}
      </select>
      <span className={"badge " + (user.is_active ? "st-done" : "st-blocked")}>
        <span className="dot" />
        {user.is_active ? t("adm_active") : t("adm_inactive")}
      </span>
      <button
        className="btn ghost"
        disabled={busy || isSelf}
        title={isSelf ? t("adm_self_guard") : undefined}
        onClick={() => {
          if (user.is_active && !confirm(t("adm_deactivate_confirm").replace("{email}", user.email))) return;
          apply({ is_active: !user.is_active });
        }}
      >
        {user.is_active ? t("adm_deactivate") : t("adm_reactivate")}
      </button>
      {err && <span className="err">{err}</span>}
    </div>
  );
}

function AgentCredRow({ agent, onChanged }: { agent: Agent; onChanged: () => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const enrolled = !!agent.token_issued_at;

  return (
    <div className="adm-row">
      <div className="adm-id">
        <div className="nm">{agent.label || agent.agent}</div>
        <div className="ds">{agent.agent}</div>
      </div>
      <span className={"badge " + (enrolled ? "st-done" : "st-waiting")}>
        <span className="dot" />
        {enrolled ? t("adm_enrolled") : t("adm_shared_secret")}
      </span>
      <span className="ds">
        {enrolled ? `${t("adm_issued")} ${new Date(agent.token_issued_at as string).toLocaleString()}` : ""}
      </span>
      <button
        className="btn ghost"
        disabled={busy || !enrolled}
        onClick={async () => {
          if (!confirm(t("adm_revoke_confirm").replace("{agent}", agent.agent))) return;
          setBusy(true); setErr(null);
          try { await revokeAgentToken(agent.agent); onChanged(); }
          catch (e) { setErr((e as Error).message); }
          finally { setBusy(false); }
        }}
      >
        {t("adm_revoke")}
      </button>
      {err && <span className="err">{err}</span>}
    </div>
  );
}

export function Admin({ meId }: { meId: string }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<"users" | "agents">("users");
  const [users, setUsers] = useState<Me[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);

  const reloadUsers = useCallback(() => { getUsers().then(setUsers).catch(() => {}); }, []);
  const reloadAgents = useCallback(() => { getAgents().then(setAgents).catch(() => {}); }, []);
  useEffect(() => { reloadUsers(); reloadAgents(); }, [reloadUsers, reloadAgents]);

  return (
    <div className="pj-page">
      <div className="adm-tabs">
        <button className={"btn " + (tab === "users" ? "primary" : "ghost")} onClick={() => setTab("users")}>{t("adm_tab_users")}</button>
        <button className={"btn " + (tab === "agents" ? "primary" : "ghost")} onClick={() => setTab("agents")}>{t("adm_tab_agents")}</button>
      </div>
      {tab === "users" ? (
        <>
          <NewUserForm onCreated={reloadUsers} />
          <div className="adm-list">
            {users.map((u) => (<UserRow key={u.id} user={u} isSelf={u.id === meId} onChanged={reloadUsers} />))}
          </div>
        </>
      ) : (
        <div className="adm-list">
          {agents.map((a) => (<AgentCredRow key={a.agent} agent={a} onChanged={reloadAgents} />))}
        </div>
      )}
    </div>
  );
}
