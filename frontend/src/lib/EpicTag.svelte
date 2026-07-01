<script lang="ts">
  import type { Epic } from "./types";

  let { epic }: { epic: Epic | undefined } = $props();

  const fallback = "#94a3b8";
</script>

{#if epic}
  <span class="epic-tag" style:--dot={epic.color ?? fallback} title={epic.title}>
    <span class="dot"></span>
    <span class="label">{epic.title}</span>
  </span>
{/if}

<style>
  .epic-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-size: 0.72rem;
    font-weight: 600;
    color: #475569;
    background: #f1f5f9;
    border-radius: 999px;
    padding: 0.1em 0.55em;
    max-width: 100%;
  }
  .dot {
    width: 0.6em;
    height: 0.6em;
    border-radius: 50%;
    background: var(--dot);
    flex: 0 0 auto;
  }
  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
