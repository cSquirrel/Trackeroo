import {
  test,
  expect,
  columnByName,
  card,
  addTaskViaBoard,
  openTask,
} from "../helpers/app";

test.describe("Blocking", () => {
  test("blocks and unblocks a task", async ({ page }) => {
    await page.goto("/");
    const title = `Blockable ${Date.now()}`;
    await addTaskViaBoard(page, "Backlog", title);

    const panel = await openTask(page, title);
    await panel.getByPlaceholder("Reason").fill("Waiting on design");
    await panel.getByRole("button", { name: "Block", exact: true }).click();
    await expect(panel.locator(".blocked-note")).toContainText("Waiting on design");
    await panel.getByRole("button", { name: /close/i }).click();

    // Card shows the blocked indicator.
    const theCard = card(columnByName(page, "Backlog"), title);
    await expect(theCard.locator(".blocked-badge")).toBeVisible();

    // Unblock and confirm the indicator clears.
    await theCard.click();
    const panel2 = page.locator('aside.panel[aria-label="Task detail"]');
    await panel2.getByRole("button", { name: "Unblock" }).click();
    await expect(panel2.locator(".blocked-note")).toHaveCount(0);
    await panel2.getByRole("button", { name: /close/i }).click();
    await expect(theCard.locator(".blocked-badge")).toHaveCount(0);
  });
});
