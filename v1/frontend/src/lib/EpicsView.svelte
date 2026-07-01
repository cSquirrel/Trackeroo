<script lang="ts">
  import * as api from "./api";
  import EpicTag from "./EpicTag.svelte";
  import { store } from "./store.svelte";
  import type { Epic } from "./types";

  let localError = $state<string | null>(null);

  // New epic form
  let newTitle = $state("");
  let newDescription = $state("");
  let newColor = $state("#4f46e5");

  // Inline edit state
  let editingId = $state<number | null>(null);
  let editTitle = $state("");
  let editDescription = $state("");
  let editColor = $state("#4f46e5");

  function fail(e: unknown) {
    localError = e instanceof Error ? e.message : String(e);
  }

  async function create() {
    if (!newTitle.trim()) return;
    try {
      await api.createEpic({
        title: newTitle.trim(),
        description: newDescription.trim() || null,
        color: newColor,
      });
      newTitle = "";
      newDescription = "";
      newColor = "#4f46e5";
      await store.refreshEpics();
    } catch (e) {
      fail(e);
    }
  }

  function startEdit(epic: Epic) {
    editingId = epic.id;
    editTitle = epic.title;
    editDescription = epic.description ?? "";
    editColor = epic.color ?? "#4f46e5";
  }

  async function saveEdit() {
    if (editingId === null) return;
    try {
      await api.updateEpic(editingId, {
        title: editTitle.trim(),
        description: editDescription.trim() || null,
        color: editColor,
      });
      editingId = null;
      await store.refreshEpics();
    } catch (e) {
      fail(e);
    }
  }

  async function remove(epic: Epic) {
    if (!confirm(`Delete epic "${epic.title}"? Tasks keep existing but lose this epic.`))
      return;
    try {
      await api.deleteEpic(epic.id);
      await Promise.all([store.refreshEpics(), store.refreshTasks()]);
    } catch (e) {
      fail(e);
    }
  }
</script>

<div class="view">
  <h1>Epics</h1>
  {#if localError}<p class="error">{localError}</p>{/if}

  <section class="create">
    <h2>New epic</h2>
    <form onsubmit={(e) => { e.preventDefault(); create(); }}>
      <input placeholder="Title" bind:value={newTitle} />
      <input placeholder="Description (optional)" bind:value={newDescription} />
      <label class="color">
        Color <input type="color" bind:value={newColor} />
      </label>
      <button type="submit" class="primary" disabled={!newTitle.trim()}>Create</button>
    </form>
  </section>

  <section class="list">
    {#if store.epics.length === 0}
      <p class="muted">No epics yet.</p>
    {/if}
    {#each store.epics as epic (epic.id)}
      <div class="epic-row">
        {#if editingId === epic.id}
          <input class="grow" bind:value={editTitle} />
          <input class="grow" bind:value={editDescription} placeholder="Description" />
          <input type="color" bind:value={editColor} />
          <button class="primary" onclick={saveEdit}>Save</button>
          <button onclick={() => (editingId = null)}>Cancel</button>
        {:else}
          <EpicTag {epic} />
          <span class="desc muted">{epic.description ?? ""}</span>
          <button onclick={() => startEdit(epic)}>Edit</button>
          <button class="danger" onclick={() => remove(epic)}>Delete</button>
        {/if}
      </div>
    {/each}
  </section>
</div>

<style>
  .view {
    max-width: 760px;
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
  .create input:not([type="color"]) {
    flex: 1 1 180px;
  }
  input:not([type="color"]) {
    font: inherit;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
  }
  .color {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: #475569;
  }
  button {
    font: inherit;
    cursor: pointer;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    padding: 0.4rem 0.7rem;
  }
  button:disabled {
    opacity: 0.5;
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
  .epic-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.6rem;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }
  .grow {
    flex: 1;
  }
  .desc {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.85rem;
  }
  .muted {
    color: #94a3b8;
  }
  .error {
    color: #b91c1c;
    background: #fee2e2;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
  }
</style>
