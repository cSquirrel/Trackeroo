import { ApiError } from "./api";

// Maps the documented dependency-add failure codes (see docs/api-contract.md
// POST /api/tasks/{id}/dependencies) to human-readable messages.
export function describeDependencyError(e: unknown): string {
  if (e instanceof ApiError) {
    switch (e.status) {
      case 400:
        return "A task can't depend on itself.";
      case 404:
        return "That task no longer exists.";
      case 409:
        return "That dependency already exists.";
      case 422:
        return "That would create a dependency cycle.";
    }
  }
  return e instanceof Error ? e.message : String(e);
}
