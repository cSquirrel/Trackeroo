<script lang="ts">
  import { confirm } from "@tauri-apps/plugin-dialog";
  import * as api from "./api";
  import { store } from "./store.svelte";
  import type { SwimLane } from "./types";

  let localError = $state<string | null>(null);
  let newName = $state("");
  let newIsDone = $state(false);

  let editingId = $state<number | null>(null);
  let editName = $state("");

  // lane whose delete is mid-confirmation (only set when it has tasks to move)
  let deletingLaneId = $state<number | null>(null);
  let moveToId = $state<number | "">("");

  function fail(e: unknown) {
    localError = e instanceof Error ? e.message : String(e);
  }

  const lanes = $derived(store.swimlanes);

  async function create() {
    if (!newName.trim()) return;
    try {
      await api.createSwimlane({ name: newName.trim(), is_done_column: newIsDone });
      newName = "";
      newIsDone = false;
      await store.refreshProject();
    } catch (e) {
      fail(e);
    }
  }

  function startEdit(lane: SwimLane) {
    editingId = lane.id;
    editName = lane.name;
  }

  async function saveEdit() {
    if (editingId === null) return;
    try {
      await api.updateSwimlane(editingId, { name: editName.trim() });
      editingId = null;
      await store.refreshProject();
    } catch (e) {
      fail(e);
    }
  }

  async function toggleDone(lane: SwimLane) {
    try {
      await api.updateSwimlane(lane.id, { is_done_column: !lane.is_done_column });
      await store.refreshProject();
    } catch (e) {
      fail(e);
    }
  }

  async function requestDelete(lane: SwimLane) {
    if (lanes.length <= 1) return; // at least one lane must always exist
    const tasks = store.tasksForSwimlane(lane.id);
    if (tasks.length === 0) {
      if (await confirm(`Delete empty column "${lane.name}"?`, { kind: "warning" })) {
        await doDelete(lane.id);
      }
      return;
    }
    deletingLaneId = lane.id;
    moveToId = lanes.find((l) => l.id !== lane.id)?.id ?? "";
  }

  function cancelDelete() {
    deletingLaneId = null;
  }

  async function confirmMoveAndDelete(lane: SwimLane) {
    if (moveToId === "") return;
    try {
      for (const t of store.tasksForSwimlane(lane.id)) {
        await api.updateTask(t.id, { swimlane_id: moveToId });
      }
      await doDelete(lane.id);
    } catch (e) {
      fail(e);
    }
  }

  async function doDelete(laneId: number) {
    try {
      await api.deleteSwimlane(laneId);
      deletingLaneId = null;
      await Promise.all([store.refreshProject(), store.refreshTasks()]);
    } catch (e) {
      fail(e);
    }
  }

  async function move(index: number, delta: number) {
    const ids = lanes.map((l) => l.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      await api.reorderSwimlanes(ids);
      await store.refreshProject();
    } catch (e) {
      fail(e);
    }
  }
</script>

<div class="view">
  <h1>Swimlane settings</h1>
  {#if localError}<p class="error">{localError}</p>{/if}

  <section class="create">
    <h2>New column</h2>
    <form onsubmit={(e) => { e.preventDefault(); create(); }}>
      <input placeholder="Column name" bind:value={newName} />
      <label class="check">
        <input type="checkbox" bind:checked={newIsDone} /> is done column
      </label>
      <button type="submit" class="primary" disabled={!newName.trim()}>Add</button>
    </form>
  </section>

  <section class="list">
    {#each lanes as lane, i (lane.id)}
      <div class="lane-row">
        <div class="order-btns">
          <button onclick={() => move(i, -1)} disabled={i === 0} title="Move up">↑</button>
          <button
            onclick={() => move(i, 1)}
            disabled={i === lanes.length - 1}
            title="Move down">↓</button
          >
        </div>

        {#if editingId === lane.id}
          <input class="grow" bind:value={editName} />
          <button class="primary" onclick={saveEdit}>Save</button>
          <button onclick={() => (editingId = null)}>Cancel</button>
        {:else if deletingLaneId === lane.id}
          <span class="grow">
            Move {store.tasksForSwimlane(lane.id).length} ticket(s) to
          </span>
          <select bind:value={moveToId}>
            {#each lanes.filter((l) => l.id !== lane.id) as other (other.id)}
              <option value={other.id}>{other.name}</option>
            {/each}
          </select>
          <button class="danger" onclick={() => confirmMoveAndDelete(lane)}>
            Move &amp; delete
          </button>
          <button onclick={cancelDelete}>Cancel</button>
        {:else}
          <span class="name">{lane.name}</span>
          <label class="check">
            <input
              type="checkbox"
              checked={lane.is_done_column}
              onchange={() => toggleDone(lane)}
            /> done
          </label>
          <button onclick={() => startEdit(lane)}>Rename</button>
          <button
            class="danger"
            onclick={() => requestDelete(lane)}
            disabled={lanes.length <= 1}
            title={lanes.length <= 1 ? "At least one lane must exist" : ""}
          >
            Delete
          </button>
        {/if}
      </div>
    {/each}
  </section>
</div>

<style>
  .view {
    max-width: 640px;
  }
  h1 {
    font-size: 1.4rem;
  }
  h2 {
    font-size: 0.95rem;
    color: #475569;
  }
  .create form {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    flex-wrap: wrap;
  }
  input:not([type="checkbox"]) {
    font: inherit;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
  }
  .create input:not([type="checkbox"]) {
    flex: 1 1 200px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.85rem;
    color: #475569;
  }
  button {
    font: inherit;
    cursor: pointer;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    padding: 0.35rem 0.6rem;
  }
  button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .primary {
    background: #4f46e5;
    border-color: #4f46e5;
    color: #fff;
  }
  .danger {
    color: #dc2626;
  }
  .list {
    margin-top: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .lane-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.6rem;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }
  .order-btns {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .order-btns button {
    padding: 0 0.4rem;
    line-height: 1.2;
  }
  .name {
    flex: 1;
    font-weight: 600;
    color: #1e293b;
  }
  .grow {
    flex: 1;
  }
  .error {
    color: #b91c1c;
    background: #fee2e2;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
  }
</style>
