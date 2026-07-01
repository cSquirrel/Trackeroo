<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { updateProject } from "./api";
  import Board from "./Board.svelte";
  import EpicsView from "./EpicsView.svelte";
  import SwimlanesView from "./SwimlanesView.svelte";
  import TaskDetailPanel from "./TaskDetailPanel.svelte";
  import { store } from "./store.svelte";

  type View = "board" | "epics" | "swimlanes";
  let view = $state<View>("board");
  let selectedTaskId = $state<number | null>(null);

  // Project name/description editing
  let editingProject = $state(false);
  let projName = $state("");
  let projDesc = $state("");

  store.loadAll();

  function openTask(id: number) {
    selectedTaskId = id;
  }

  async function onTaskChanged() {
    await store.refreshTasks();
  }

  function startEditProject() {
    projName = store.project?.name ?? "";
    projDesc = store.project?.description ?? "";
    editingProject = true;
  }

  async function saveProject() {
    try {
      store.project = await updateProject({
        name: projName.trim(),
        description: projDesc.trim() || null,
      });
      editingProject = false;
    } catch (e) {
      store.error = e instanceof Error ? e.message : String(e);
    }
  }

  // Launch a brand-new, independent OS process that shows its own picker. The
  // current window/project is unaffected — there is no in-window switching.
  async function openOtherProject() {
    try {
      await invoke("open_new_window");
    } catch (e) {
      store.error = e instanceof Error ? e.message : String(e);
    }
  }
</script>

<div class="app">
  <header class="topbar">
    <div class="brand">
      {#if editingProject}
        <input class="proj-name" bind:value={projName} />
        <input class="proj-desc" bind:value={projDesc} placeholder="Description" />
        <button class="primary" onclick={saveProject}>Save</button>
        <button class="ghost" onclick={() => (editingProject = false)}>Cancel</button>
      {:else}
        <h1>{store.project?.name ?? "Trackeroo"}</h1>
        {#if store.project?.description}
          <span class="proj-sub">{store.project.description}</span>
        {/if}
        <button class="ghost small" onclick={startEditProject}>edit</button>
      {/if}
    </div>

    <nav>
      <button class:active={view === "board"} onclick={() => (view = "board")}>Board</button>
      <button class:active={view === "epics"} onclick={() => (view = "epics")}>Epics</button>
      <button class:active={view === "swimlanes"} onclick={() => (view = "swimlanes")}>
        Swimlanes
      </button>
      <button class="open-other" onclick={openOtherProject} title="Open another project in a new window">
        Open project…
      </button>
    </nav>

    <label class="author">
      Name
      <input
        placeholder="you"
        value={store.author}
        oninput={(e) => store.setAuthor(e.currentTarget.value)}
      />
    </label>
  </header>

  {#if store.error}
    <div class="banner-error">
      {store.error}
      <button class="ghost" onclick={() => (store.error = null)}>dismiss</button>
    </div>
  {/if}

  <main>
    {#if view === "board"}
      <Board onopen={openTask} />
    {:else if view === "epics"}
      <EpicsView />
    {:else}
      <SwimlanesView />
    {/if}
  </main>

  {#if selectedTaskId !== null}
    <TaskDetailPanel
      taskId={selectedTaskId}
      onclose={() => (selectedTaskId = null)}
      onchanged={onTaskChanged}
    />
  {/if}
</div>

<style>
  .app {
    min-height: 100vh;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0.8rem 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    background: #fff;
    flex-wrap: wrap;
  }
  .brand {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .brand h1 {
    margin: 0;
    font-size: 1.25rem;
    color: #1e293b;
  }
  .proj-sub {
    color: #94a3b8;
    font-size: 0.85rem;
  }
  .proj-name,
  .proj-desc {
    font: inherit;
    padding: 0.3rem 0.4rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
  }
  nav {
    display: flex;
    gap: 0.3rem;
    margin-left: auto;
  }
  nav button {
    font: inherit;
    cursor: pointer;
    border: 1px solid transparent;
    background: transparent;
    color: #475569;
    border-radius: 6px;
    padding: 0.4rem 0.8rem;
  }
  nav button.active {
    background: #eef2ff;
    color: #4f46e5;
    font-weight: 600;
  }
  nav button.open-other {
    border: 1px solid #cbd5e1;
    margin-left: 0.6rem;
  }
  .author {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
    color: #64748b;
  }
  .author input {
    font: inherit;
    padding: 0.3rem 0.4rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    width: 8ch;
  }
  button.primary {
    background: #4f46e5;
    border: 1px solid #4f46e5;
    color: #fff;
    border-radius: 6px;
    padding: 0.35rem 0.7rem;
    cursor: pointer;
    font: inherit;
  }
  button.ghost {
    background: none;
    border: none;
    color: #64748b;
    cursor: pointer;
    text-decoration: underline;
    font: inherit;
  }
  button.small {
    font-size: 0.75rem;
  }
  .banner-error {
    background: #fee2e2;
    color: #b91c1c;
    padding: 0.5rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    font-size: 0.85rem;
  }
  main {
    padding: 1.5rem;
  }
</style>
