<script lang="ts">
  import { updater } from "./update.svelte";

  // Only render for states the user should see. A silent (non-manual) check
  // that is still running or found nothing shows nothing at all.
  let visible = $derived(
    updater.phase === "available" ||
      updater.phase === "downloading" ||
      updater.phase === "installing" ||
      (updater.manual &&
        (updater.phase === "checking" ||
          updater.phase === "uptodate" ||
          updater.phase === "error")),
  );

  function pct(): number {
    if (!updater.total) return 0;
    return Math.min(100, Math.round((updater.downloaded / updater.total) * 100));
  }

  function mb(bytes: number): string {
    return (bytes / (1024 * 1024)).toFixed(1);
  }
</script>

{#if visible}
  <div class="update-banner" class:err={updater.phase === "error"}>
    {#if updater.phase === "checking"}
      <span class="msg">Checking for updates…</span>
    {:else if updater.phase === "available"}
      <span class="msg">
        <strong>Trackeroo {updater.newVersion}</strong> is available.
      </span>
      <div class="actions">
        <button class="primary" onclick={() => updater.downloadAndInstall()}>
          Update &amp; restart
        </button>
        <button class="ghost" onclick={() => updater.dismiss()}>Later</button>
      </div>
    {:else if updater.phase === "downloading"}
      <span class="msg">
        Downloading update…
        {#if updater.total}
          {mb(updater.downloaded)} / {mb(updater.total)} MB ({pct()}%)
        {/if}
      </span>
      <div class="bar"><div class="fill" style:width={`${pct()}%`}></div></div>
    {:else if updater.phase === "installing"}
      <span class="msg">Installing update — the app will restart…</span>
    {:else if updater.phase === "uptodate"}
      <span class="msg">You're on the latest version.</span>
      <div class="actions">
        <button class="ghost" onclick={() => updater.dismiss()}>Dismiss</button>
      </div>
    {:else if updater.phase === "error"}
      <span class="msg">Update failed: {updater.error}</span>
      <div class="actions">
        <button class="ghost" onclick={() => updater.dismiss()}>Dismiss</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .update-banner {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    padding: 0.6rem 1.5rem;
    background: #eef2ff;
    border-bottom: 1px solid #c7d2fe;
    color: #3730a3;
    font-size: 0.9rem;
  }
  .update-banner.err {
    background: #fee2e2;
    border-bottom-color: #fecaca;
    color: #b91c1c;
  }
  .msg {
    flex: 1;
    min-width: 12rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  button {
    font: inherit;
    cursor: pointer;
    border-radius: 6px;
    padding: 0.35rem 0.7rem;
  }
  button.primary {
    background: #4f46e5;
    border: 1px solid #4f46e5;
    color: #fff;
  }
  button.ghost {
    background: none;
    border: none;
    color: inherit;
    text-decoration: underline;
  }
  .bar {
    flex-basis: 100%;
    height: 6px;
    background: #c7d2fe;
    border-radius: 3px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: #4f46e5;
    transition: width 0.2s ease;
  }
</style>
