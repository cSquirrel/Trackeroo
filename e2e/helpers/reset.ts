import type { APIRequestContext } from "@playwright/test";

// The five swimlanes the backend seeds on first boot. resetToSeed normalizes
// the board back to exactly these before each test so tests are independent of
// each other's mutations and of run order.
export const DEFAULT_SWIMLANES: { name: string; is_done_column: boolean }[] = [
  { name: "Backlog", is_done_column: false },
  { name: "To Do", is_done_column: false },
  { name: "In Progress", is_done_column: false },
  { name: "Review", is_done_column: false },
  { name: "Done", is_done_column: true },
];

interface Lane {
  id: number;
  name: string;
  position: number;
  is_done_column: boolean;
}

async function json<T>(p: Promise<{ json(): Promise<T> }>): Promise<T> {
  return (await p).json();
}

// Reset the whole board to the seeded default: no tasks, no epics, and exactly
// the five default swimlanes in order. Done purely through the REST API.
export async function resetToSeed(request: APIRequestContext): Promise<void> {
  // Tasks (deleting a task cascades its comments, links, and dependency rows).
  const tasks = await json<{ id: number }[]>(request.get("/api/tasks"));
  for (const t of tasks) await request.delete(`/api/tasks/${t.id}`);

  // Epics.
  const epics = await json<{ id: number }[]>(request.get("/api/epics"));
  for (const e of epics) await request.delete(`/api/epics/${e.id}`);

  // Swimlanes: patch the first N existing lanes to the defaults, create any
  // missing ones, and delete any extras beyond the five defaults.
  const project = await json<{ swimlanes: Lane[] }>(request.get("/api/project"));
  const lanes = [...project.swimlanes].sort((a, b) => a.position - b.position);

  for (let i = 0; i < DEFAULT_SWIMLANES.length; i++) {
    const want = DEFAULT_SWIMLANES[i];
    if (i < lanes.length) {
      await request.patch(`/api/swimlanes/${lanes[i].id}`, {
        data: { name: want.name, position: i, is_done_column: want.is_done_column },
      });
    } else {
      await request.post("/api/swimlanes", {
        data: { name: want.name, position: i, is_done_column: want.is_done_column },
      });
    }
  }

  for (let i = DEFAULT_SWIMLANES.length; i < lanes.length; i++) {
    await request.delete(`/api/swimlanes/${lanes[i].id}`);
  }
}
