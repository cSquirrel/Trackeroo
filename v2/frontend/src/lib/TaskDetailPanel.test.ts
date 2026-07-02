import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { store } from "./store.svelte";
import TaskDetailPanel from "./TaskDetailPanel.svelte";
import type { Task, TaskDetail } from "./types";

vi.mock("./api", () => ({
  getTask: vi.fn(),
  updateTask: vi.fn(),
  blockTask: vi.fn(),
  unblockTask: vi.fn(),
  addComment: vi.fn(),
  deleteComment: vi.fn(),
  addLink: vi.fn(),
  removeLink: vi.fn(),
  addDependency: vi.fn(),
  removeDependency: vi.fn(),
}));

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 10,
    epic_id: null,
    swimlane_id: 2,
    title: "Login form",
    description: null,
    type: null,
    position: 0,
    is_blocked: false,
    blocked_reason: null,
    created_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

function makeDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    ...makeTask(),
    comments: [],
    links: [],
    dependencies: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();

  store.project = null;
  store.epics = [];
  store.tasks = [];
  store.author = "";

  vi.mocked(api.getTask).mockResolvedValue(makeDetail());
  vi.mocked(api.blockTask).mockResolvedValue(
    makeTask({ is_blocked: true, blocked_reason: "design" }),
  );
  vi.mocked(api.unblockTask).mockResolvedValue(makeTask());
  vi.mocked(api.addComment).mockResolvedValue({
    id: 1,
    task_id: 10,
    author: "tester",
    body: "nice",
    kind: "comment",
    created_at: "2026-07-01T13:00:00Z",
  });
});

function props() {
  return { taskId: 10, onclose: vi.fn(), onchanged: vi.fn() };
}

describe("TaskDetailPanel", () => {
  it("loads the task detail on open and populates the title", async () => {
    render(TaskDetailPanel, { props: props() });
    await waitFor(() => expect(api.getTask).toHaveBeenCalledWith(10));
    expect(await screen.findByDisplayValue("Login form")).toBeTruthy();
  });

  it("blocks the task with the entered reason", async () => {
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    await fireEvent.input(screen.getByPlaceholderText("Reason"), {
      target: { value: "design" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Block" }));

    await waitFor(() => expect(api.blockTask).toHaveBeenCalledWith(10, "design"));
  });

  it("shows unblock control and calls unblockTask for a blocked task", async () => {
    vi.mocked(api.getTask).mockResolvedValue(
      makeDetail({ is_blocked: true, blocked_reason: "waiting on design" }),
    );
    render(TaskDetailPanel, { props: props() });

    const unblockBtn = await screen.findByRole("button", { name: "Unblock" });
    await fireEvent.click(unblockBtn);
    await waitFor(() => expect(api.unblockTask).toHaveBeenCalledWith(10));
  });

  it("submits a comment with the current author and default kind", async () => {
    store.setAuthor("tester");
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    await fireEvent.input(screen.getByPlaceholderText("Write a comment…"), {
      target: { value: "nice work" },
    });
    const addBtn = screen
      .getAllByRole("button", { name: "Add" })
      .find((b) => !(b as HTMLButtonElement).disabled)!;
    await fireEvent.click(addBtn);

    await waitFor(() =>
      expect(api.addComment).toHaveBeenCalledWith(10, {
        author: "tester",
        body: "nice work",
        kind: "comment",
      }),
    );
  });

  it("shows rendered markdown by default and switches to the editor via Edit", async () => {
    vi.mocked(api.getTask).mockResolvedValue(
      makeDetail({ description: "**bold** text" }),
    );
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    expect(document.querySelector(".markdown-body strong")?.textContent).toBe("bold");
    expect(screen.queryByPlaceholderText("Markdown supported…")).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByPlaceholderText("Markdown supported…")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Edit" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Preview" })).toBeTruthy();
  });

  it("renders the Preview tab from the in-progress edit, not the saved value", async () => {
    vi.mocked(api.getTask).mockResolvedValue(makeDetail({ description: "old" }));
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await fireEvent.input(screen.getByPlaceholderText("Markdown supported…"), {
      target: { value: "# heading" },
    });
    await fireEvent.click(screen.getByRole("tab", { name: "Preview" }));

    expect(document.querySelector(".markdown-body h1")?.textContent).toBe("heading");
  });

  it("Cancel discards the in-progress description edit", async () => {
    vi.mocked(api.getTask).mockResolvedValue(makeDetail({ description: "original" }));
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await fireEvent.input(screen.getByPlaceholderText("Markdown supported…"), {
      target: { value: "discard me" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByPlaceholderText("Markdown supported…")).toBeNull();
    expect(document.querySelector(".markdown-body")?.textContent?.trim()).toBe("original");
  });

  it("blocks comment submission when no author is set", async () => {
    render(TaskDetailPanel, { props: props() });
    await screen.findByDisplayValue("Login form");

    await fireEvent.input(screen.getByPlaceholderText("Write a comment…"), {
      target: { value: "no author yet" },
    });
    const addBtn = screen
      .getAllByRole("button", { name: "Add" })
      .find((b) => !(b as HTMLButtonElement).disabled)!;
    await fireEvent.click(addBtn);

    expect(api.addComment).not.toHaveBeenCalled();
    expect(screen.getByText(/Set your name/i)).toBeTruthy();
  });
});
