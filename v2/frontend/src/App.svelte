<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { setApiBaseUrl, updateProject } from "./lib/api";
  import BoardApp from "./lib/BoardApp.svelte";
  import ProjectPicker from "./lib/ProjectPicker.svelte";
  import Spinner from "./lib/Spinner.svelte";

  type LaunchTarget = { path: string | null; error: string | null };

  // Three phases: while "checking" we resolve any CLI launch path (to avoid a
  // picker flash before an auto-open); then either the board or the picker.
  let phase = $state<"checking" | "picker" | "board">("checking");
  // True only while auto-opening a CLI-supplied project, so we show a spinner
  // during that (~9s) wait instead of a blank window. The no-arg check is fast,
  // so it stays false and "checking" renders nothing (no flash).
  let openingCli = $state(false);
  // Surfaced in the picker when a launch arg was invalid, so a bad path doesn't
  // fail silently.
  let launchError = $state<string | null>(null);

  async function onProjectOpened(port: number, newName?: string) {
    setApiBaseUrl(`http://localhost:${port}/api`);
    // For a freshly created project the backend seeds a default name; override
    // it with what the user typed so the board title matches.
    if (newName) {
      try {
        await updateProject({ name: newName });
      } catch {
        // Non-fatal: fall back to the default seeded name.
      }
    }
    phase = "board";
  }

  onMount(async () => {
    let target: LaunchTarget = { path: null, error: null };
    try {
      target = await invoke<LaunchTarget>("get_launch_target");
    } catch {
      // Ignore: treat as no launch arg.
    }
    if (target.path) {
      // Launched with a project path — open it directly (create=true so a fresh
      // folder becomes a new project; an existing trackeroo.db just loads).
      openingCli = true;
      try {
        const port = await invoke<number>("open_project", {
          path: target.path,
          create: true,
          name: null,
        });
        await onProjectOpened(port);
        return;
      } catch (e) {
        launchError = e instanceof Error ? e.message : String(e);
        openingCli = false;
      }
    } else if (target.error) {
      launchError = target.error;
    }
    phase = "picker";
  });
</script>

{#if phase === "board"}
  <BoardApp />
{:else if phase === "picker"}
  <ProjectPicker onopened={onProjectOpened} initialError={launchError} />
{:else if openingCli}
  <div class="launch-loading">
    <Spinner label="Opening project" />
  </div>
{/if}

<style>
  .launch-loading {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f1f5f9;
  }
</style>
