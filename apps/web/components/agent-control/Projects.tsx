"use client";

// Écrans projets & tâches (P8) : liste API + création (manage_projects), détail
// avec tâches. 100% API-driven, tenant-scoped côté serveur, capacité-gated côté
// UI (l'API vérifie toujours). États loading/empty/erreur/offline via <States>.
import { useState } from "react";

import {
  useCreateProject,
  useCreateTask,
  useProject,
  useProjectTasks,
  useProjects,
} from "@/lib/agent-control/hooks";
import { useAgentControl } from "@/lib/agent-control/provider";
import { AcApiError } from "@/lib/agent-control/client";
import { AcEmpty, AcError, AcLoading } from "./States";

const STATUS_TONE: Record<string, string> = {
  in_dev: "text-emerald-400",
  proposed: "text-neutral-300",
  validated: "text-sky-400",
  done: "text-sky-400",
  archived: "text-neutral-500",
};

export function Projects({ onOpen }: { onOpen: (id: string) => void }) {
  const { t, can } = useAgentControl();
  const q = useProjects();
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-100">{t("nav_projects")}</h2>
        {can("manage_projects") && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500"
          >
            {t("create_project")}
          </button>
        )}
      </div>

      {open && can("manage_projects") && <CreateProjectForm onDone={() => setOpen(false)} />}

      {q.isLoading ? (
        <AcLoading />
      ) : q.isError ? (
        <AcError error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data || q.data.items.length === 0 ? (
        <AcEmpty />
      ) : (
        <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800">
          {q.data.items.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onOpen(p.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-start hover:bg-neutral-900"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm text-neutral-100">{p.name}</span>
                  <span className="block truncate text-xs text-neutral-500">
                    {p.slug}
                    {p.is_seed ? ` · ${t("seed_badge")}` : ""}
                  </span>
                </span>
                <span className="flex items-center gap-3 text-xs">
                  <span className="text-neutral-500">{p.task_count} · {t("tasks")}</span>
                  <span className={STATUS_TONE[p.status] ?? "text-neutral-400"}>{p.status}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CreateProjectForm({ onDone }: { onDone: () => void }) {
  const { t } = useAgentControl();
  const m = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const err = m.error instanceof AcApiError ? m.error.message : null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate(
          { name, description: description || null } as never,
          { onSuccess: onDone },
        );
      }}
      className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4"
    >
      <label className="block text-sm">
        <span className="mb-1 block text-neutral-400">{t("project_name")}</span>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-neutral-400">{t("description")}</span>
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
        />
      </label>
      {err && <div className="text-xs text-red-400" role="alert">{err}</div>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={m.isPending}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {t("create")}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300"
        >
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}

const TASK_TONE: Record<string, string> = {
  todo: "text-neutral-400",
  in_progress: "text-emerald-400",
  blocked: "text-amber-400",
  done: "text-sky-400",
};

export function ProjectDetail({ projectId }: { projectId: string }) {
  const { t, can } = useAgentControl();
  const q = useProject(projectId);
  const tasks = useProjectTasks(projectId);
  const [open, setOpen] = useState(false);

  if (q.isLoading) return <AcLoading />;
  if (q.isError) return <AcError error={q.error} onRetry={() => void q.refetch()} />;
  const p = q.data;
  if (!p) return <AcLoading />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">{p.name}</h2>
        <p className="text-xs text-neutral-500">
          <span className={STATUS_TONE[p.status] ?? "text-neutral-400"}>{p.status}</span> · {p.slug}
          {p.is_seed ? ` · ${t("seed_badge")}` : ""}
        </p>
        {p.description && <p className="mt-2 text-sm text-neutral-300">{p.description}</p>}
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-neutral-300">{t("tasks")}</h3>
          {can("manage_projects") && !p.is_seed && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="rounded-md border border-neutral-700 px-2.5 py-1 text-xs text-neutral-200 hover:bg-neutral-800"
            >
              {t("add_task")}
            </button>
          )}
        </div>

        {open && can("manage_projects") && (
          <CreateTaskForm projectId={projectId} onDone={() => setOpen(false)} />
        )}

        {tasks.isLoading ? (
          <AcLoading />
        ) : tasks.isError ? (
          <AcError error={tasks.error} onRetry={() => void tasks.refetch()} />
        ) : !tasks.data || tasks.data.items.length === 0 ? (
          <AcEmpty />
        ) : (
          <ul className="divide-y divide-neutral-800 rounded-xl border border-neutral-800">
            {tasks.data.items.map((task) => (
              <li key={task.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className="min-w-0">
                  <span className="block truncate text-neutral-100">
                    {task.parent_id ? "↳ " : ""}
                    {task.code ? `${task.code} · ` : ""}
                    {task.title}
                  </span>
                  {task.agent_key && (
                    <span className="block truncate text-xs text-neutral-500">{task.agent_key}</span>
                  )}
                </span>
                <span className={`text-xs ${TASK_TONE[task.status] ?? "text-neutral-400"}`}>
                  {task.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CreateTaskForm({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const { t } = useAgentControl();
  const m = useCreateTask(projectId);
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");

  const err = m.error instanceof AcApiError ? m.error.message : null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate(
          { title, code: code || null } as never,
          { onSuccess: onDone },
        );
      }}
      className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4"
    >
      <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <label className="block text-sm">
          <span className="mb-1 block text-neutral-400">{t("task_title")}</span>
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-neutral-400">{t("task_code")}</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-neutral-100"
          />
        </label>
      </div>
      {err && <div className="text-xs text-red-400" role="alert">{err}</div>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={m.isPending}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {t("create")}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300"
        >
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}
