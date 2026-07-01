import {
  test,
  expect,
  columnNames,
  columnByName,
  card,
  addTaskViaBoard,
} from "../helpers/app";

test.describe("Board", () => {
  test("@smoke loads with the five seeded columns in order", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".board .column")).toHaveCount(5);
    expect(await columnNames(page)).toEqual([
      "Backlog",
      "To Do",
      "In Progress",
      "Review",
      "Done",
    ]);
    await expect(columnByName(page, "Done").locator(".done-pill")).toBeVisible();
  });

  test("@smoke creates a task from the board", async ({ page }) => {
    await page.goto("/");
    const title = `Smoke task ${Date.now()}`;
    await addTaskViaBoard(page, "Backlog", title);
    await expect(card(columnByName(page, "Backlog"), title)).toBeVisible();
  });
});
