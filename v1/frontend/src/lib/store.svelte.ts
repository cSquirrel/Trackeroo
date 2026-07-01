// Global reactive app state + data-loading actions, using Svelte 5 runes.
import * as api from "./api";
import type { Epic, Project, SwimLane, Task } from "./types";

class Store {
  project = $state<Project | null>(null);
  epics = $state<Epic[]>([]);
  tasks = $state<Task[]>([]);
  loading = $state(false);
  error = $state<string | null>(null);

  // Persisted author name used when posting comments.
  author = $state<string>(localStorage.getItem("trackeroo.author") ?? "");

  get swimlanes(): SwimLane[] {
    return [...(this.project?.swimlanes ?? [])].sort(
      (a, b) => a.position - b.position,
    );
  }

  setAuthor(name: string) {
    this.author = name;
    localStorage.setItem("trackeroo.author", name);
  }

  epicById(id: number | null): Epic | undefined {
    if (id === null) return undefined;
    return this.epics.find((e) => e.id === id);
  }

  tasksForSwimlane(swimlaneId: number): Task[] {
    return this.tasks
      .filter((t) => t.swimlane_id === swimlaneId)
      .sort((a, b) => a.position - b.position);
  }

  async loadAll() {
    this.loading = true;
    this.error = null;
    try {
      const [project, epics, tasks] = await Promise.all([
        api.getProject(),
        api.listEpics(),
        api.listTasks(),
      ]);
      this.project = project;
      this.epics = epics;
      this.tasks = tasks;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }

  async refreshTasks() {
    this.tasks = await api.listTasks();
  }

  async refreshEpics() {
    this.epics = await api.listEpics();
  }

  async refreshProject() {
    this.project = await api.getProject();
  }

  upsertTask(task: Task) {
    const idx = this.tasks.findIndex((t) => t.id === task.id);
    if (idx >= 0) this.tasks[idx] = task;
    else this.tasks.push(task);
  }

  removeTask(id: number) {
    this.tasks = this.tasks.filter((t) => t.id !== id);
  }
}

export const store = new Store();
