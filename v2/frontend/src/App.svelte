<script lang="ts">
  import { setApiBaseUrl, updateProject } from "./lib/api";
  import BoardApp from "./lib/BoardApp.svelte";
  import ProjectPicker from "./lib/ProjectPicker.svelte";

  // Gate: show the project picker until a project has been opened (a backend
  // spawned and healthy on a dynamic port). No data loads until then — the
  // picker itself needs no backend.
  let ready = $state(false);

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
    ready = true;
  }
</script>

{#if ready}
  <BoardApp />
{:else}
  <ProjectPicker onopened={onProjectOpened} />
{/if}
