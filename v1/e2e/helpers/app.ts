import { test as base, expect, type Locator, type Page } from "@playwright/test";
import { resetToSeed } from "./reset";

// Every test starts from a freshly seeded board (5 default swimlanes, no tasks,
// no epics). This runs via the REST API before the test body navigates.
export const test = base.extend<{ seeded: void }>({
  seeded: [
    async ({ request }, use) => {
      await resetToSeed(request);
      await use();
    },
    { auto: true },
  ],
});

export { expect };

function exact(text: string): RegExp {
  return new RegExp(`^${text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
}

// A board column (`<section class="column">`) selected by its header name.
export function columnByName(page: Page, name: string): Locator {
  return page.locator(".column", {
    has: page.locator(".col-name", { hasText: exact(name) }),
  });
}

// The ordered list of column header names currently on the board.
export async function columnNames(page: Page): Promise<string[]> {
  return page.locator(".board .column .col-name").allInnerTexts();
}

export function card(scope: Page | Locator, title: string): Locator {
  return scope.locator(".card", { hasText: title });
}

// Set the author name (top-right) — required before posting comments.
export async function setAuthor(page: Page, name: string): Promise<void> {
  await page.locator(".author input").fill(name);
}

// Create a task from the board's per-column "+ Add task" form.
export async function addTaskViaBoard(
  page: Page,
  columnName: string,
  title: string,
): Promise<void> {
  const col = columnByName(page, columnName);
  await col.getByRole("button", { name: "+ Add task" }).click();
  await col.getByPlaceholder("Task title").fill(title);
  await col.getByRole("button", { name: "Add", exact: true }).click();
  await expect(card(col, title)).toBeVisible();
}

// Open a task's detail panel by clicking its card, and return the panel locator.
export async function openTask(page: Page, title: string): Promise<Locator> {
  await card(page, title).click();
  const panel = page.locator('aside.panel[aria-label="Task detail"]');
  await expect(panel).toBeVisible();
  return panel;
}
