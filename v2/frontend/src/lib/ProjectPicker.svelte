<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { open } from "@tauri-apps/plugin-dialog";
  import { onMount } from "svelte";
  import Spinner from "./Spinner.svelte";

  type RecentProject = { path: string; name: string };

  // Called once a backend has been spawned and is healthy. `newName` is the
  // display name for a freshly created project (so the board title reflects it).
  // `initialError` is shown on first render (e.g. an invalid CLI launch path).
  let {
    onopened,
    initialError = null,
  }: {
    onopened: (port: number, newName?: string) => void;
    initialError?: string | null;
  } = $props();

  let recent = $state<RecentProject[]>([]);
  let newName = $state("");
  let busy = $state(false);
  let busyLabel = $state("Opening project…");
  let error = $state<string | null>(null);

  onMount(async () => {
    error = initialError;
    try {
      recent = await invoke<RecentProject[]>("list_recent_projects");
    } catch {
      recent = [];
    }
  });

  async function spawnFor(
    path: string,
    create: boolean,
    label: string,
    name?: string,
  ) {
    busy = true;
    busyLabel = label;
    error = null;
    try {
      const port = await invoke<number>("open_project", { path, create, name });
      onopened(port, create ? name : undefined);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      busy = false;
    }
  }

  async function createProject() {
    const name = newName.trim();
    if (!name) {
      error = "Enter a project name first.";
      return;
    }
    if (/[/\\]/.test(name)) {
      error = "Project name cannot contain slashes.";
      return;
    }
    const parent = await open({
      directory: true,
      multiple: false,
      title: "Choose where to create the project folder",
    });
    if (typeof parent !== "string") return; // cancelled
    const path = `${parent.replace(/\/$/, "")}/${name}`;
    await spawnFor(path, true, "Creating project…", name);
  }

  async function openExisting() {
    const dir = await open({
      directory: true,
      multiple: false,
      title: "Open a Trackeroo project folder",
    });
    if (typeof dir !== "string") return; // cancelled
    await spawnFor(dir, false, "Opening project…");
  }

  async function openRecent(r: RecentProject) {
    await spawnFor(r.path, false, "Opening project…");
  }
</script>

<div class="picker">
  <div class="card">
    <h1>Trackeroo</h1>
    <p class="sub">Open a project to get started. Each project is just a folder
      containing a <code>trackeroo.db</code> file.</p>

    {#if error}
      <div class="err">{error}</div>
    {/if}

    <section class="new">
      <h2>New project</h2>
      <div class="row">
        <input
          class="name"
          placeholder="Project name"
          bind:value={newName}
          disabled={busy}
          onkeydown={(e) => e.key === "Enter" && createProject()}
        />
        <button class="primary" onclick={createProject} disabled={busy}>
          Choose location & create…
        </button>
      </div>
    </section>

    <section class="open">
      <h2>Open existing</h2>
      <button class="secondary" onclick={openExisting} disabled={busy}>
        Open project folder…
      </button>
    </section>

    <section class="recent">
      <h2>Recent projects</h2>
      {#if recent.length === 0}
        <p class="empty">No recent projects yet.</p>
      {:else}
        <ul>
          {#each recent as r (r.path)}
            <li>
              <button class="recent-item" onclick={() => openRecent(r)} disabled={busy}>
                <span class="r-name">{r.name}</span>
                <span class="r-path">{r.path}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    {#if busy}
      <div class="overlay">
        <Spinner label={busyLabel} />
      </div>
    {/if}
  </div>
</div>

<style>
  .picker {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f1f5f9;
    padding: 2rem;
  }
  .card {
    position: relative;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 2rem;
    width: 100%;
    max-width: 520px;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  }
  .overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.85);
    border-radius: 12px;
  }
  h1 {
    margin: 0;
    color: #1e293b;
  }
  .sub {
    color: #64748b;
    font-size: 0.9rem;
    margin: 0.3rem 0 1.2rem;
  }
  code {
    background: #f1f5f9;
    padding: 0.05rem 0.3rem;
    border-radius: 4px;
  }
  h2 {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #94a3b8;
    margin: 1.2rem 0 0.5rem;
  }
  .row {
    display: flex;
    gap: 0.5rem;
  }
  .name {
    flex: 1;
    font: inherit;
    padding: 0.5rem 0.6rem;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
  }
  button {
    font: inherit;
    cursor: pointer;
    border-radius: 8px;
    padding: 0.5rem 0.8rem;
  }
  button:disabled {
    opacity: 0.6;
    cursor: default;
  }
  button.primary {
    background: #4f46e5;
    border: 1px solid #4f46e5;
    color: #fff;
    white-space: nowrap;
  }
  button.secondary {
    background: #fff;
    border: 1px solid #cbd5e1;
    color: #334155;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .recent-item {
    width: 100%;
    text-align: left;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .recent-item:hover:not(:disabled) {
    background: #eef2ff;
    border-color: #c7d2fe;
  }
  .r-name {
    color: #1e293b;
    font-weight: 600;
  }
  .r-path {
    color: #94a3b8;
    font-size: 0.75rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    color: #94a3b8;
    font-size: 0.85rem;
  }
  .err {
    background: #fee2e2;
    color: #b91c1c;
    padding: 0.5rem 0.7rem;
    border-radius: 8px;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
  }
</style>
