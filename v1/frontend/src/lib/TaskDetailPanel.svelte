<script lang="ts">
  import * as api from "./api";
  import { describeDependencyError } from "./errors";
  import EpicTag from "./EpicTag.svelte";
  import { store } from "./store.svelte";
  import type {
    Comment,
    CommentKind,
    LinkType,
    Task,
    TaskDetail,
    TaskLink,
  } from "./types";

  let {
    taskId,
    onclose,
    onchanged,
  }: {
    taskId: number;
    onclose: () => void;
    onchanged: () => void;
  } = $props();

  let detail = $state<TaskDetail | null>(null);
  let loading = $state(false);
  let localError = $state<string | null>(null);

  // Editable fields
  let title = $state("");
  let description = $state("");
  let epicId = $state<number | "none">("none");

  // Comment form
  let commentBody = $state("");
  let commentKind = $state<CommentKind>("comment");

  // Block form
  let blockReason = $state("");

  // Link form
  let linkUrl = $state("");
  let linkLabel = $state("");
  let linkType = $state<LinkType>("pr");

  // Dependency form
  let dependsOnId = $state<number | "">("");

  async function load() {
    loading = true;
    localError = null;
    try {
      const d = await api.getTask(taskId);
      detail = d;
      title = d.title;
      description = d.description ?? "";
      epicId = d.epic_id ?? "none";
    } catch (e) {
      localError = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void taskId;
    load();
  });

  function fail(e: unknown) {
    localError = e instanceof Error ? e.message : String(e);
  }

  async function saveFields() {
    if (!detail) return;
    try {
      const updated = await api.updateTask(detail.id, {
        title: title.trim() || detail.title,
        description: description.trim() ? description : null,
        epic_id: epicId === "none" ? null : epicId,
      });
      store.upsertTask(updated);
      await load();
      onchanged();
    } catch (e) {
      fail(e);
    }
  }

  async function block() {
    if (!detail || !blockReason.trim()) return;
    try {
      const updated = await api.blockTask(detail.id, blockReason.trim());
      store.upsertTask(updated);
      blockReason = "";
      await load();
      onchanged();
    } catch (e) {
      fail(e);
    }
  }

  async function unblock() {
    if (!detail) return;
    try {
      const updated = await api.unblockTask(detail.id);
      store.upsertTask(updated);
      await load();
      onchanged();
    } catch (e) {
      fail(e);
    }
  }

  async function addComment() {
    if (!detail || !commentBody.trim()) return;
    if (!store.author.trim()) {
      localError = "Set your name (top-right) before commenting.";
      return;
    }
    try {
      await api.addComment(detail.id, {
        author: store.author.trim(),
        body: commentBody.trim(),
        kind: commentKind,
      });
      commentBody = "";
      await load();
    } catch (e) {
      fail(e);
    }
  }

  async function deleteComment(c: Comment) {
    if (!detail) return;
    if (!confirm("Delete this comment?")) return;
    try {
      await api.deleteComment(detail.id, c.id);
      await load();
    } catch (e) {
      fail(e);
    }
  }

  async function addLink() {
    if (!detail || !linkUrl.trim()) return;
    try {
      await api.addLink(detail.id, {
        url: linkUrl.trim(),
        label: linkLabel.trim() || null,
        link_type: linkType,
      });
      linkUrl = "";
      linkLabel = "";
      await load();
    } catch (e) {
      fail(e);
    }
  }

  async function removeLink(link: TaskLink) {
    if (!detail) return;
    if (!confirm(`Remove link "${link.label ?? link.url}"?`)) return;
    try {
      await api.removeLink(detail.id, link.id);
      await load();
    } catch (e) {
      fail(e);
    }
  }

  async function addDependency() {
    if (!detail || dependsOnId === "") return;
    try {
      await api.addDependency(detail.id, dependsOnId);
      dependsOnId = "";
      await load();
      onchanged();
    } catch (e) {
      localError = describeDependencyError(e);
    }
  }

  async function removeDependency(dependencyId: number) {
    if (!detail) return;
    if (!confirm("Remove this dependency?")) return;
    try {
      await api.removeDependency(detail.id, dependencyId);
      await load();
      onchanged();
    } catch (e) {
      fail(e);
    }
  }

  function isTaskDone(t: Task | undefined): boolean {
    if (!t) return false;
    const lane = store.swimlanes.find((l) => l.id === t.swimlane_id);
    return lane?.is_done_column ?? false;
  }

  const otherTasks = $derived(
    store.tasks.filter((t) => t.id !== taskId),
  );
</script>

<div class="backdrop" onclick={onclose} role="presentation"></div>
<aside class="panel" aria-label="Task detail">
  <header class="panel-head">
    <h2>Task #{taskId}</h2>
    <button class="link" onclick={onclose}>close ✕</button>
  </header>

  {#if localError}
    <p class="error">{localError}</p>
  {/if}

  {#if loading && !detail}
    <p class="muted">Loading…</p>
  {:else if detail}
    <div class="body">
      <!-- Core fields -->
      <section>
        <label class="field">
          <span>Title</span>
          <input bind:value={title} />
        </label>
        <label class="field">
          <span>Description</span>
          <textarea rows="4" bind:value={description}></textarea>
        </label>
        <label class="field">
          <span>Epic</span>
          <select bind:value={epicId}>
            <option value="none">— none —</option>
            {#each store.epics as epic (epic.id)}
              <option value={epic.id}>{epic.title}</option>
            {/each}
          </select>
        </label>
        <button class="primary" onclick={saveFields}>Save changes</button>
      </section>

      <!-- Block / unblock -->
      <section>
        <h3>Blocking</h3>
        {#if detail.is_blocked}
          <p class="blocked-note">
            Blocked{detail.blocked_reason ? `: ${detail.blocked_reason}` : ""}
          </p>
          <button onclick={unblock}>Unblock</button>
        {:else}
          <div class="inline-form">
            <input placeholder="Reason" bind:value={blockReason} />
            <button onclick={block} disabled={!blockReason.trim()}>Block</button>
          </div>
        {/if}
      </section>

      <!-- Dependencies -->
      <section>
        <h3>Dependencies</h3>
        {#if detail.dependencies.length === 0}
          <p class="muted">No dependencies.</p>
        {:else}
          <ul class="dep-list">
            {#each detail.dependencies as dep (dep.id)}
              {@const dt = store.tasks.find((t) => t.id === dep.depends_on_task_id)}
              <li>
                <span class="dep-status" class:done={isTaskDone(dt)}>
                  {isTaskDone(dt) ? "done" : "open"}
                </span>
                <span class="dep-title">
                  #{dep.depends_on_task_id} {dt ? dt.title : "(unknown task)"}
                </span>
                <button class="link danger" onclick={() => removeDependency(dep.id)}>
                  remove
                </button>
              </li>
            {/each}
          </ul>
        {/if}
        <div class="inline-form">
          <select bind:value={dependsOnId}>
            <option value="">Add dependency…</option>
            {#each otherTasks as t (t.id)}
              <option value={t.id}>#{t.id} {t.title}</option>
            {/each}
          </select>
          <button onclick={addDependency} disabled={dependsOnId === ""}>Add</button>
        </div>
      </section>

      <!-- Links -->
      <section>
        <h3>Links</h3>
        {#if detail.links.length === 0}
          <p class="muted">No links.</p>
        {:else}
          <ul class="link-list">
            {#each detail.links as link (link.id)}
              <li>
                <span class="link-type">{link.link_type}</span>
                <a href={link.url} target="_blank" rel="noopener noreferrer">
                  {link.label || link.url}
                </a>
                <button class="link danger" onclick={() => removeLink(link)}>
                  remove
                </button>
              </li>
            {/each}
          </ul>
        {/if}
        <div class="link-form">
          <input placeholder="https://…" bind:value={linkUrl} />
          <input placeholder="Label (optional)" bind:value={linkLabel} />
          <select bind:value={linkType}>
            <option value="pr">PR</option>
            <option value="slack">Slack</option>
            <option value="other">Other</option>
          </select>
          <button onclick={addLink} disabled={!linkUrl.trim()}>Add link</button>
        </div>
      </section>

      <!-- Comments / annotations -->
      <section>
        <h3>Comments &amp; annotations</h3>
        {#if detail.comments.length === 0}
          <p class="muted">No comments yet.</p>
        {:else}
          <ul class="comment-list">
            {#each detail.comments as c (c.id)}
              <li class="comment" class:annotation={c.kind === "annotation"}>
                <div class="comment-head">
                  <strong>{c.author}</strong>
                  <span class="kind-pill">{c.kind}</span>
                  <span class="ts">{new Date(c.created_at).toLocaleString()}</span>
                  <button class="link danger" onclick={() => deleteComment(c)}>
                    delete
                  </button>
                </div>
                <p class="comment-body">{c.body}</p>
              </li>
            {/each}
          </ul>
        {/if}
        <div class="comment-form">
          <textarea rows="2" placeholder="Write a comment…" bind:value={commentBody}
          ></textarea>
          <div class="comment-actions">
            <label class="kind-toggle">
              <input type="checkbox" checked={commentKind === "annotation"}
                onchange={(e) =>
                  (commentKind = e.currentTarget.checked ? "annotation" : "comment")}
              />
              annotation
            </label>
            <button class="primary" onclick={addComment} disabled={!commentBody.trim()}>
              Add
            </button>
          </div>
        </div>
      </section>

      <p class="meta">
        {#if detail.epic_id}<EpicTag epic={store.epicById(detail.epic_id)} />{/if}
        <span class="muted small">
          Updated {new Date(detail.updated_at).toLocaleString()}
        </span>
      </p>
    </div>
  {/if}
</aside>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.35);
    z-index: 40;
  }
  .panel {
    position: fixed;
    top: 0;
    right: 0;
    width: min(460px, 100vw);
    height: 100vh;
    background: #fff;
    border-left: 1px solid #e2e8f0;
    box-shadow: -8px 0 24px rgba(15, 23, 42, 0.12);
    z-index: 41;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.2rem;
    border-bottom: 1px solid #e2e8f0;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 1.05rem;
  }
  .body {
    overflow-y: auto;
    padding: 1rem 1.2rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 1.4rem;
  }
  section h3 {
    margin: 0 0 0.5rem;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748b;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    margin-bottom: 0.7rem;
    font-size: 0.8rem;
    color: #475569;
  }
  input,
  textarea,
  select {
    font: inherit;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    width: 100%;
    box-sizing: border-box;
  }
  textarea {
    resize: vertical;
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
  .link {
    background: none;
    border: none;
    color: #4f46e5;
    padding: 0;
    text-decoration: underline;
  }
  .link.danger {
    color: #dc2626;
  }
  .inline-form,
  .link-form {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }
  .inline-form input,
  .inline-form select {
    flex: 1;
  }
  .link-form input {
    flex: 1 1 100%;
  }
  .dep-list,
  .link-list,
  .comment-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .dep-list li,
  .link-list li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
  }
  .dep-status {
    font-size: 0.6rem;
    text-transform: uppercase;
    font-weight: 700;
    color: #b45309;
    background: #fef3c7;
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }
  .dep-status.done {
    color: #047857;
    background: #d1fae5;
  }
  .dep-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .link-type {
    font-size: 0.6rem;
    text-transform: uppercase;
    font-weight: 700;
    color: #475569;
    background: #e2e8f0;
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }
  .link-list a {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #2563eb;
  }
  .comment {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.5rem 0.6rem;
  }
  .comment.annotation {
    background: #fffbeb;
    border-color: #fde68a;
  }
  .comment-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: #64748b;
  }
  .kind-pill {
    font-size: 0.6rem;
    text-transform: uppercase;
    background: #e2e8f0;
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }
  .ts {
    margin-left: auto;
  }
  .comment-body {
    margin: 0.3rem 0 0;
    font-size: 0.85rem;
    color: #1e293b;
    white-space: pre-wrap;
  }
  .comment-form {
    margin-top: 0.6rem;
  }
  .comment-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.4rem;
  }
  .kind-toggle {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.8rem;
    color: #475569;
    width: auto;
  }
  .kind-toggle input {
    width: auto;
  }
  .blocked-note {
    color: #b91c1c;
    background: #fee2e2;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    font-size: 0.85rem;
    margin: 0 0 0.5rem;
  }
  .error {
    color: #b91c1c;
    background: #fee2e2;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    margin: 0.6rem 1.2rem 0;
    font-size: 0.85rem;
  }
  .muted {
    color: #94a3b8;
  }
  .small {
    font-size: 0.72rem;
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
</style>
