import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { ApiError } from "./api";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
  } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  // The base URL is a runtime value (set per-project from the dynamic backend
  // port); pin it to the relative "/api" prefix these assertions expect.
  api.setApiBaseUrl("/api");
  fetchMock = vi.fn().mockResolvedValue(response({}));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function lastCall(): [string, RequestInit] {
  const calls = fetchMock.mock.calls;
  return calls[calls.length - 1] as [string, RequestInit];
}

function bodyOf(init: RequestInit): unknown {
  return init.body ? JSON.parse(init.body as string) : undefined;
}

describe("api client — URL, method, and body", () => {
  it("getProject issues GET /api/project with no body", async () => {
    fetchMock.mockResolvedValueOnce(response({ id: 1, name: "T", swimlanes: [] }));
    await api.getProject();
    const [url, init] = lastCall();
    expect(url).toBe("/api/project");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("updateProject issues PATCH /api/project with JSON body + content-type", async () => {
    await api.updateProject({ name: "New", description: null });
    const [url, init] = lastCall();
    expect(url).toBe("/api/project");
    expect(init.method).toBe("PATCH");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
    expect(bodyOf(init)).toEqual({ name: "New", description: null });
  });

  it("createSwimlane POSTs /api/swimlanes", async () => {
    await api.createSwimlane({ name: "QA", is_done_column: true });
    const [url, init] = lastCall();
    expect(url).toBe("/api/swimlanes");
    expect(init.method).toBe("POST");
    expect(bodyOf(init)).toEqual({ name: "QA", is_done_column: true });
  });

  it("updateSwimlane PATCHes /api/swimlanes/{id}", async () => {
    await api.updateSwimlane(6, { name: "QA2" });
    const [url, init] = lastCall();
    expect(url).toBe("/api/swimlanes/6");
    expect(init.method).toBe("PATCH");
    expect(bodyOf(init)).toEqual({ name: "QA2" });
  });

  it("deleteSwimlane DELETEs /api/swimlanes/{id}", async () => {
    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await api.deleteSwimlane(6);
    const [url, init] = lastCall();
    expect(url).toBe("/api/swimlanes/6");
    expect(init.method).toBe("DELETE");
  });

  it("reorderSwimlanes POSTs ordered_ids to /api/swimlanes/reorder", async () => {
    fetchMock.mockResolvedValueOnce(response([]));
    await api.reorderSwimlanes([3, 1, 2]);
    const [url, init] = lastCall();
    expect(url).toBe("/api/swimlanes/reorder");
    expect(init.method).toBe("POST");
    expect(bodyOf(init)).toEqual({ ordered_ids: [3, 1, 2] });
  });

  it("listEpics GETs /api/epics", async () => {
    fetchMock.mockResolvedValueOnce(response([]));
    await api.listEpics();
    const [url, init] = lastCall();
    expect(url).toBe("/api/epics");
    expect(init.method).toBe("GET");
  });

  it("createEpic POSTs /api/epics", async () => {
    await api.createEpic({ title: "Auth", color: "#fff" });
    const [url, init] = lastCall();
    expect(url).toBe("/api/epics");
    expect(bodyOf(init)).toEqual({ title: "Auth", color: "#fff" });
  });

  it("getEpic / updateEpic / deleteEpic hit /api/epics/{id}", async () => {
    await api.getEpic(2);
    expect(lastCall()[0]).toBe("/api/epics/2");
    expect(lastCall()[1].method).toBe("GET");

    await api.updateEpic(2, { title: "X" });
    expect(lastCall()[0]).toBe("/api/epics/2");
    expect(lastCall()[1].method).toBe("PATCH");

    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await api.deleteEpic(2);
    expect(lastCall()[0]).toBe("/api/epics/2");
    expect(lastCall()[1].method).toBe("DELETE");
  });

  it("listTasks encodes filters as query params", async () => {
    fetchMock.mockResolvedValueOnce(response([]));
    await api.listTasks({ epic_id: 1, swimlane_id: 2 });
    expect(lastCall()[0]).toBe("/api/tasks?epic_id=1&swimlane_id=2");
  });

  it("listTasks with no filters omits the query string", async () => {
    fetchMock.mockResolvedValueOnce(response([]));
    await api.listTasks();
    expect(lastCall()[0]).toBe("/api/tasks");
  });

  it("createTask POSTs /api/tasks", async () => {
    await api.createTask({ title: "T", swimlane_id: 2 });
    const [url, init] = lastCall();
    expect(url).toBe("/api/tasks");
    expect(bodyOf(init)).toEqual({ title: "T", swimlane_id: 2 });
  });

  it("getTask GETs /api/tasks/{id}", async () => {
    fetchMock.mockResolvedValueOnce(
      response({ id: 10, comments: [], links: [], dependencies: [] }),
    );
    await api.getTask(10);
    expect(lastCall()[0]).toBe("/api/tasks/10");
    expect(lastCall()[1].method).toBe("GET");
  });

  it("updateTask PATCHes /api/tasks/{id}", async () => {
    await api.updateTask(10, { title: "New" });
    expect(lastCall()[0]).toBe("/api/tasks/10");
    expect(lastCall()[1].method).toBe("PATCH");
    expect(bodyOf(lastCall()[1])).toEqual({ title: "New" });
  });

  it("moveTask POSTs swimlane_id + position to /move", async () => {
    await api.moveTask(10, 5, 0);
    const [url, init] = lastCall();
    expect(url).toBe("/api/tasks/10/move");
    expect(init.method).toBe("POST");
    expect(bodyOf(init)).toEqual({ swimlane_id: 5, position: 0 });
  });

  it("blockTask POSTs reason; unblockTask sends no body", async () => {
    await api.blockTask(10, "waiting");
    expect(lastCall()[0]).toBe("/api/tasks/10/block");
    expect(bodyOf(lastCall()[1])).toEqual({ reason: "waiting" });

    await api.unblockTask(10);
    expect(lastCall()[0]).toBe("/api/tasks/10/unblock");
    expect(lastCall()[1].method).toBe("POST");
    expect(lastCall()[1].body).toBeUndefined();
  });

  it("addDependency POSTs depends_on_task_id", async () => {
    fetchMock.mockResolvedValueOnce(
      response({ id: 4, task_id: 10, depends_on_task_id: 7 }, 201),
    );
    await api.addDependency(10, 7);
    const [url, init] = lastCall();
    expect(url).toBe("/api/tasks/10/dependencies");
    expect(bodyOf(init)).toEqual({ depends_on_task_id: 7 });
  });

  it("removeDependency DELETEs the dependency row by id", async () => {
    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await api.removeDependency(10, 4);
    expect(lastCall()[0]).toBe("/api/tasks/10/dependencies/4");
    expect(lastCall()[1].method).toBe("DELETE");
  });

  it("addLink / removeLink hit /api/tasks/{id}/links", async () => {
    await api.addLink(10, { url: "https://x", link_type: "pr" });
    expect(lastCall()[0]).toBe("/api/tasks/10/links");
    expect(bodyOf(lastCall()[1])).toEqual({ url: "https://x", link_type: "pr" });

    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await api.removeLink(10, 2);
    expect(lastCall()[0]).toBe("/api/tasks/10/links/2");
    expect(lastCall()[1].method).toBe("DELETE");
  });

  it("addComment / listComments / deleteComment hit /api/tasks/{id}/comments", async () => {
    await api.addComment(10, { author: "me", body: "hi", kind: "annotation" });
    expect(lastCall()[0]).toBe("/api/tasks/10/comments");
    expect(bodyOf(lastCall()[1])).toEqual({
      author: "me",
      body: "hi",
      kind: "annotation",
    });

    fetchMock.mockResolvedValueOnce(response([]));
    await api.listComments(10);
    expect(lastCall()[0]).toBe("/api/tasks/10/comments");
    expect(lastCall()[1].method).toBe("GET");

    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await api.deleteComment(10, 3);
    expect(lastCall()[0]).toBe("/api/tasks/10/comments/3");
    expect(lastCall()[1].method).toBe("DELETE");
  });
});

describe("api client — response handling", () => {
  it("parses and returns the JSON body on success", async () => {
    const project = { id: 1, name: "Trackeroo", description: null, swimlanes: [] };
    fetchMock.mockResolvedValueOnce(response(project));
    await expect(api.getProject()).resolves.toEqual(project);
  });

  it("returns undefined for 204 without reading a body", async () => {
    fetchMock.mockResolvedValueOnce(response(undefined, 204));
    await expect(api.deleteTask(1)).resolves.toBeUndefined();
  });

  it("throws ApiError with status + detail on error responses", async () => {
    fetchMock.mockResolvedValue(response({ detail: "not found" }, 404));
    const err = await api.getTask(999).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.detail).toBe("not found");
  });

  it("surfaces 422 cycle errors from addDependency as ApiError", async () => {
    fetchMock.mockResolvedValue(response({ detail: "cycle" }, 422));
    const err = await api.addDependency(1, 2).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.detail).toBe("cycle");
  });
});
