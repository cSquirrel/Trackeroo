import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TaskCard from "./TaskCard.svelte";
import { store } from "./store.svelte";
import type { Epic, Task } from "./types";

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

const epic: Epic = {
  id: 1,
  title: "Auth",
  description: null,
  color: "#4f46e5",
  created_at: "2026-07-01T12:00:00Z",
};

beforeEach(() => {
  store.epics = [epic];
  store.tasks = [];
});

describe("TaskCard", () => {
  it("renders the task title", () => {
    render(TaskCard, { props: { task: makeTask(), onopen: vi.fn() } });
    expect(screen.getByText("Login form")).toBeTruthy();
  });

  it("shows the epic color tag when the task has an epic", () => {
    render(TaskCard, { props: { task: makeTask({ epic_id: 1 }), onopen: vi.fn() } });
    expect(screen.getByText("Auth")).toBeTruthy();
  });

  it("omits the epic tag when the task has no epic", () => {
    render(TaskCard, { props: { task: makeTask({ epic_id: null }), onopen: vi.fn() } });
    expect(screen.queryByText("Auth")).toBeNull();
  });

  it("shows the type badge only when a type is set", () => {
    const { unmount } = render(TaskCard, {
      props: { task: makeTask({ type: null }), onopen: vi.fn() },
    });
    expect(screen.queryByText("chore")).toBeNull();
    unmount();

    render(TaskCard, { props: { task: makeTask({ type: "chore" }), onopen: vi.fn() } });
    expect(screen.getByText("chore")).toBeTruthy();
  });

  it("renders a blocked indicator only when the task is blocked", () => {
    const { unmount } = render(TaskCard, {
      props: { task: makeTask(), onopen: vi.fn() },
    });
    expect(screen.queryByText("blocked")).toBeNull();
    unmount();

    render(TaskCard, {
      props: {
        task: makeTask({ is_blocked: true, blocked_reason: "waiting" }),
        onopen: vi.fn(),
      },
    });
    expect(screen.getByText("blocked")).toBeTruthy();
  });

  it("calls onopen with the task id when clicked", async () => {
    const onopen = vi.fn();
    render(TaskCard, { props: { task: makeTask({ id: 42 }), onopen } });
    await fireEvent.click(screen.getByRole("button"));
    expect(onopen).toHaveBeenCalledWith(42);
  });
});
