<script lang="ts">
  import EpicTag from "./EpicTag.svelte";
  import { store } from "./store.svelte";
  import type { Task } from "./types";

  let { task, onopen }: { task: Task; onopen: (id: number) => void } = $props();

  const epic = $derived(store.epicById(task.epic_id));
</script>

<button
  type="button"
  class="card"
  class:blocked={task.is_blocked}
  onclick={() => onopen(task.id)}
>
  <div class="title-row">
    <span class="title">{task.title}</span>
    {#if task.is_blocked}
      <span class="blocked-badge" title={task.blocked_reason ?? "Blocked"}>
        blocked
      </span>
    {/if}
  </div>
  {#if epic || task.type}
    <div class="tags">
      {#if task.type}<span class="type-badge">{task.type}</span>{/if}
      {#if epic}<EpicTag {epic} />{/if}
    </div>
  {/if}
</button>

<style>
  .card {
    display: block;
    width: 100%;
    text-align: left;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.6rem 0.7rem;
    cursor: grab;
    font: inherit;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
  }
  .card:hover {
    border-color: #94a3b8;
  }
  .card.blocked {
    border-left-color: #ef4444;
  }
  .title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.4rem;
  }
  .title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #1e293b;
    line-height: 1.25;
  }
  .blocked-badge {
    flex: 0 0 auto;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #b91c1c;
    background: #fee2e2;
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }
  .tags {
    margin-top: 0.45rem;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
  }
  .type-badge {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #475569;
    background: #f1f5f9;
    border-radius: 4px;
    padding: 0.1em 0.4em;
  }
</style>
