// Typed HTTP client for the Trackeroo REST API (docs/api-contract.md).
// Base URL defaults to same-origin `/api` so it works when served by the
// backend in Docker; override for local dev via VITE_API_BASE_URL.

import type {
  Comment,
  CommentCreate,
  Epic,
  EpicCreate,
  EpicUpdate,
  Project,
  ProjectUpdate,
  SwimLane,
  SwimLaneCreate,
  SwimLaneUpdate,
  Task,
  TaskCreate,
  TaskDependency,
  TaskDetail,
  TaskLink,
  TaskLinkCreate,
  TaskMoveResult,
  TaskUpdate,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  query?: Record<string, string | number | undefined>,
): Promise<T> {
  let url = `${BASE_URL}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const res = await fetch(url, init);

  if (res.status === 204) return undefined as T;

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new ApiError(res.status, detail, `${method} ${path} failed (${res.status})`);
  }

  return payload as T;
}

// ---- Project ----
export const getProject = () => request<Project>("GET", "/project");
export const updateProject = (body: ProjectUpdate) =>
  request<Project>("PATCH", "/project", body);

// ---- Swimlanes ----
export const createSwimlane = (body: SwimLaneCreate) =>
  request<SwimLane>("POST", "/swimlanes", body);
export const updateSwimlane = (id: number, body: SwimLaneUpdate) =>
  request<SwimLane>("PATCH", `/swimlanes/${id}`, body);
export const deleteSwimlane = (id: number) =>
  request<void>("DELETE", `/swimlanes/${id}`);
export const reorderSwimlanes = (orderedIds: number[]) =>
  request<SwimLane[]>("POST", "/swimlanes/reorder", { ordered_ids: orderedIds });

// ---- Epics ----
export const listEpics = () => request<Epic[]>("GET", "/epics");
export const createEpic = (body: EpicCreate) =>
  request<Epic>("POST", "/epics", body);
export const getEpic = (id: number) => request<Epic>("GET", `/epics/${id}`);
export const updateEpic = (id: number, body: EpicUpdate) =>
  request<Epic>("PATCH", `/epics/${id}`, body);
export const deleteEpic = (id: number) => request<void>("DELETE", `/epics/${id}`);

// ---- Tasks ----
export const listTasks = (filters?: { epic_id?: number; swimlane_id?: number }) =>
  request<Task[]>("GET", "/tasks", undefined, filters);
export const createTask = (body: TaskCreate) =>
  request<Task>("POST", "/tasks", body);
export const getTask = (id: number) => request<TaskDetail>("GET", `/tasks/${id}`);
export const updateTask = (id: number, body: TaskUpdate) =>
  request<Task>("PATCH", `/tasks/${id}`, body);
export const deleteTask = (id: number) => request<void>("DELETE", `/tasks/${id}`);
export const moveTask = (id: number, swimlaneId: number, position: number) =>
  request<TaskMoveResult>("POST", `/tasks/${id}/move`, {
    swimlane_id: swimlaneId,
    position,
  });
export const blockTask = (id: number, reason: string) =>
  request<Task>("POST", `/tasks/${id}/block`, { reason });
export const unblockTask = (id: number) =>
  request<Task>("POST", `/tasks/${id}/unblock`);

// ---- Dependencies ----
export const addDependency = (id: number, dependsOnTaskId: number) =>
  request<TaskDependency>("POST", `/tasks/${id}/dependencies`, {
    depends_on_task_id: dependsOnTaskId,
  });
export const removeDependency = (id: number, dependencyId: number) =>
  request<void>("DELETE", `/tasks/${id}/dependencies/${dependencyId}`);

// ---- Links ----
export const addLink = (id: number, body: TaskLinkCreate) =>
  request<TaskLink>("POST", `/tasks/${id}/links`, body);
export const removeLink = (id: number, linkId: number) =>
  request<void>("DELETE", `/tasks/${id}/links/${linkId}`);

// ---- Comments ----
export const addComment = (id: number, body: CommentCreate) =>
  request<Comment>("POST", `/tasks/${id}/comments`, body);
export const listComments = (id: number) =>
  request<Comment[]>("GET", `/tasks/${id}/comments`);
export const deleteComment = (id: number, commentId: number) =>
  request<void>("DELETE", `/tasks/${id}/comments/${commentId}`);
