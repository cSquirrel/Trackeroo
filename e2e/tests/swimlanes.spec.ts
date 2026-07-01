import { test, expect, columnNames } from "../helpers/app";

test.describe("Swimlane configuration", () => {
  test("adds, renames, reorders, and deletes swimlanes", async ({ page }) => {
    // Deleting a swimlane pops a confirm() dialog.
    page.on("dialog", (d) => d.accept());

    await page.goto("/");
    await page.getByRole("button", { name: "Swimlanes" }).click();

    // Add a new column.
    await page.getByPlaceholder("Column name").fill("QA");
    await page.locator(".create").getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.locator(".lane-row", { hasText: "QA" })).toBeVisible();

    // The board reflects the new column.
    await page.getByRole("button", { name: "Board" }).click();
    expect(await columnNames(page)).toContain("QA");
    await page.getByRole("button", { name: "Swimlanes" }).click();

    // Rename Backlog -> Inbox. Once in edit mode the row shows an input (its
    // value is no longer matchable as text), so switch to the editing row.
    await page
      .locator(".lane-row", { hasText: "Backlog" })
      .getByRole("button", { name: "Rename" })
      .click();
    const editingRow = page.locator(".lane-row", {
      has: page.locator("input.grow"),
    });
    await editingRow.locator("input.grow").fill("Inbox");
    await editingRow.getByRole("button", { name: "Save" }).click();
    await expect(page.locator(".lane-row", { hasText: "Inbox" })).toBeVisible();

    // Reorder: move the last lane up one slot.
    const orderBefore = await page.locator(".lane-row .name").allInnerTexts();
    await page
      .locator(".lane-row")
      .last()
      .locator('button[title="Move up"]')
      .click();
    await expect
      .poll(() => page.locator(".lane-row .name").allInnerTexts())
      .not.toEqual(orderBefore);

    // Delete a lane.
    await page
      .locator(".lane-row", { hasText: "Review" })
      .getByRole("button", { name: "Delete" })
      .click();
    await expect(page.locator(".lane-row", { hasText: "Review" })).toHaveCount(0);

    // The board reflects every change: order matches, renames/adds/deletes applied.
    const settingsOrder = await page.locator(".lane-row .name").allInnerTexts();
    await page.getByRole("button", { name: "Board" }).click();
    const boardOrder = await columnNames(page);
    expect(boardOrder).toEqual(settingsOrder);
    expect(boardOrder).toContain("QA");
    expect(boardOrder).toContain("Inbox");
    expect(boardOrder).not.toContain("Backlog");
    expect(boardOrder).not.toContain("Review");
  });
});
