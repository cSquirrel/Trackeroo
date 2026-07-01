<script lang="ts">
  import { dndzone, type DndEvent } from "svelte-dnd-action";
  import * as api from "./api";
  import { store } from "./store.svelte";
  import TaskCard from "./TaskCard.svelte";
  import type { SwimLane, Task } from "./types";

  let { onopen }: { onopen: (id: number) => void } = $props();

  let epicFilter = $state<number | "all">("all");
  let columns = $state<{ lane: SwimLane; items: Task[] }[]>([]);
  let dragging = false;
  let warnings = $state<string[]>([]);
  let newTaskLane = $state<number | null>(null);
  let newTaskTitle = $state("");

  function matchesFilter(t: Task): boolean {
    return epicFilter === "all" || t.epic_id === epicFilter;
  }

  function rebuild() {
    columns = store.swimlanes.map((lane) => ({
      lane,
      items: store.tasksForSwimlane(lane.id).filter(matchesFilter),
    }));
  }

  $effect(() => {
    // Re-read reactive deps so the effect re-runs when data/filter change.
    void store.tasks;
    void store.project;
    void epicFilter;
    if (!dragging) rebuild();
  });

  function handleConsider(laneId: number, e: CustomEvent<DndEvent<Task>>) {
    dragging = true;
    const col = columns.find((c) => c.lane.id === laneId);
    if (col) col.items = e.detail.items;
  }

  async function handleFinalize(laneId: number, e: CustomEvent<DndEvent<Task>>) {
    const col = columns.find((c) => c.lane.id === laneId);
    if (col) col.items = e.detail.items;
    dragging = false;

    const movedId = e.detail.info.id as unknown as number;
    const index = e.detail.items.findIndex((t) => t.id === movedId);
    if (index < 0) return; // this is the source zone; target zone handles the move

    try {
      const result = await api.moveTask(movedId, laneId, index);
      store.upsertTask(result);
      warnings = result.warnings;
    } catch (err) {
      store.error = err instanceof Error ? err.message : String(err);
    } finally {
      await store.refreshTasks();
      rebuild();
    }
  }

  async function addTask(laneId: number) {
    const title = newTaskTitle.trim();
    if (!title) return;
    try {
      const task = await api.createTask({ title, swimlane_id: laneId });
      store.upsertTask(task);
      newTaskTitle = "";
      newTaskLane = null;
      rebuild();
    } catch (err) {
      store.error = err instanceof Error ? err.message : String(err);
    }
  }
</script>

<div class="toolbar">
  <label>
    Filter by epic
    <select bind:value={epicFilter}>
      <option value="all">All epics</option>
      {#each store.epics as epic (epic.id)}
        <option value={epic.id}>{epic.title}</option>
      {/each}
    </select>
  </label>
  {#if store.loading}<span class="muted">Loading…</span>{/if}
</div>

{#if warnings.length}
  <div class="warnings" role="status">
    <strong>Heads up:</strong>
    <ul>
      {#each warnings as w}<li>{w}</li>{/each}
    </ul>
    <button class="link" onclick={() => (warnings = [])}>dismiss</button>
  </div>
{/if}

<div class="board">
  {#each columns as col (col.lane.id)}
    <section class="column">
      <header class="col-head">
        <span class="col-name">{col.lane.name}</span>
        {#if col.lane.is_done_column}<span class="done-pill">done</span>{/if}
        <span class="count">{col.items.length}</span>
      </header>

      <div
        class="dropzone"
        use:dndzone={{ items: col.items, flipDurationMs: 150, dropTargetStyle: {} }}
        onconsider={(e) => handleConsider(col.lane.id, e)}
        onfinalize={(e) => handleFinalize(col.lane.id, e)}
      >
        {#each col.items as task (task.id)}
          <div class="card-wrap">
            <TaskCard {task} {onopen} />
          </div>
        {/each}
      </div>

      {#if newTaskLane === col.lane.id}
        <form class="add-form" onsubmit={(e) => { e.preventDefault(); addTask(col.lane.id); }}>
          <!-- svelte-ignore a11y_autofocus -->
          <input placeholder="Task title" bind:value={newTaskTitle} autofocus />
          <div class="add-actions">
            <button type="submit" class="primary">Add</button>
            <button type="button" class="link" onclick={() => (newTaskLane = null)}>
              cancel
            </button>
          </div>
        </form>
      {:else}
        <button
          class="add-btn"
          onclick={() => { newTaskLane = col.lane.id; newTaskTitle = ""; }}
        >
          + Add task
        </button>
      {/if}
    </section>
  {/each}
</div>

<style>
  .toolbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .toolbar label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: #475569;
  }
  .muted {
    color: #94a3b8;
    font-size: 0.85rem;
  }
  .warnings {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 1rem;
    font-size: 0.85rem;
    color: #92400e;
  }
  .warnings ul {
    margin: 0.3rem 0 0.2rem 1rem;
  }
  .board {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    overflow-x: auto;
    padding-bottom: 1rem;
  }
  .column {
    flex: 0 0 280px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.6rem;
    display: flex;
    flex-direction: column;
  }
  .col-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0.3rem 0.6rem;
    font-weight: 700;
    color: #334155;
    font-size: 0.9rem;
  }
  .done-pill {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #047857;
    background: #d1fae5;
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }
  .count {
    margin-left: auto;
    font-size: 0.75rem;
    color: #94a3b8;
    background: #e2e8f0;
    border-radius: 999px;
    padding: 0 0.5em;
  }
  .dropzone {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-height: 40px;
  }
  .card-wrap {
    outline: none;
  }
  .add-btn {
    margin-top: 0.5rem;
    background: transparent;
    border: 1px dashed #cbd5e1;
    color: #64748b;
    border-radius: 8px;
    padding: 0.4rem;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .add-btn:hover {
    background: #f1f5f9;
  }
  .add-form {
    margin-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .add-form input {
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font: inherit;
  }
  .add-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
