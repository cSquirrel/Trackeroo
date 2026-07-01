import {
  test,
  expect,
  columnByName,
  card,
  addTaskViaBoard,
  openTask,
} from "../helpers/app";

test.describe("Epics", () => {
  test("create an epic then assign a task to it from the board", async ({ page }) => {
    await page.goto("/");

    // Create an epic with a distinct color in the Epics view.
    await page.getByRole("button", { name: "Epics" }).click();
    const epicTitle = "Checkout revamp";
    const color = "#22c55e";
    await page.getByPlaceholder("Title").fill(epicTitle);
    await page.locator('input[type="color"]').evaluate((el, v) => {
      (el as HTMLInputElement).value = v as string;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }, color);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.locator(".epic-row", { hasText: epicTitle })).toBeVisible();

    // Create a task from the board and assign it to the epic.
    await page.getByRole("button", { name: "Board" }).click();
    const taskTitle = "Wire up checkout";
    await addTaskViaBoard(page, "To Do", taskTitle);

    const panel = await openTask(page, taskTitle);
    const epicSelect = panel
      .locator("label.field", { hasText: "Epic" })
      .locator("select");
    await epicSelect.selectOption({ label: epicTitle });
    await panel.getByRole("button", { name: "Save changes" }).click();
    await panel.getByRole("button", { name: /close/i }).click();

    // The card now shows the epic's color tag.
    const tag = card(columnByName(page, "To Do"), taskTitle).locator(".epic-tag");
    await expect(tag.locator(".label")).toHaveText(epicTitle);
    await expect(tag).toHaveAttribute("style", /--dot:\s*#22c55e/);
  });
});
