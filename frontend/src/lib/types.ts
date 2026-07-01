// TypeScript shapes mirroring docs/api-contract.md and backend/app/schemas.py.

export type LinkType = "pr" | "slack" | "other";
export type CommentKind = "comment" | "annotation";

export interface Project {
  id: number;
  name: string;
  description: string | null;
  swimlanes: SwimLane[];
}

export interface SwimLane {
  id: number;
  project_id: number;
  name: string;
  position: number;
  is_done_column: boolean;
}

export interface Epic {
  id: number;
  title: string;
  description: string | null;
  color: string | null;
  created_at: string;
}

export interface Task {
  id: number;
  epic_id: number | null;
  swimlane_id: number;
  title: string;
  description: string | null;
  position: number;
  is_blocked: boolean;
  blocked_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskLink {
  id: number;
  task_id: number;
  url: string;
  label: string | null;
  link_type: LinkType;
}

export interface Comment {
  id: number;
  task_id: number;
  author: string;
  body: string;
  kind: CommentKind;
  created_at: string;
}

export interface TaskDetail extends Task {
  comments: Comment[];
  links: TaskLink[];
  dependency_ids: number[];
}

export interface TaskDependency {
  id: number;
  task_id: number;
  depends_on_task_id: number;
}

export interface TaskMoveResult extends Task {
  warnings: string[];
}

// ---- Request payloads ----

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
}

export interface SwimLaneCreate {
  name: string;
  position?: number;
  is_done_column?: boolean;
}

export interface SwimLaneUpdate {
  name?: string;
  position?: number;
  is_done_column?: boolean;
}

export interface EpicCreate {
  title: string;
  description?: string | null;
  color?: string | null;
}

export interface EpicUpdate {
  title?: string;
  description?: string | null;
  color?: string | null;
}

export interface TaskCreate {
  title: string;
  swimlane_id: number;
  epic_id?: number | null;
  description?: string | null;
  position?: number;
}

export interface TaskUpdate {
  title?: string;
  description?: string | null;
  epic_id?: number | null;
  swimlane_id?: number;
  position?: number;
  is_blocked?: boolean;
  blocked_reason?: string | null;
}

export interface TaskMove {
  swimlane_id: number;
  position: number;
}

export interface TaskLinkCreate {
  url: string;
  label?: string | null;
  link_type?: LinkType;
}

export interface CommentCreate {
  author: string;
  body: string;
  kind?: CommentKind;
}
