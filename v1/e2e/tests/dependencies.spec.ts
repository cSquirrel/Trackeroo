import {
  test,
  expect,
  columnByName,
  card,
  addTaskViaBoard,
  openTask,
} from "../helpers/app";
import { dragCardTo } from "../helpers/dnd";

test.describe("Dependencies", () => {
  test("surfaces a warning when moving a dependent task into Done", async ({
    page,
  }) => {
    await page.goto("/");
    const dependency = "Provision database";
    const dependent = "Deploy service";
    await addTaskViaBoard(page, "Backlog", dependency);
    await addTaskViaBoard(page, "Backlog", dependent);

    // Make `dependent` depend on `dependency`.
    const panel = await openTask(page, dependent);
    const depSection = panel.locator("section").filter({ hasText: "Dependencies" });
    const optionValue = await depSection
      .locator("select option", { hasText: dependency })
      .getAttribute("value");
    await depSection.locator("select").selectOption(optionValue!);
    await depSection.getByRole("button", { name: "Add", exact: true }).click();
    await expect(depSection.locator(".dep-list")).toContainText(dependency);
    await panel.getByRole("button", { name: /close/i }).click();

    // Move `dependent` into Done while `dependency` is still open.
    const dependentCard = card(columnByName(page, "Backlog"), dependent);
    const doneZone = columnByName(page, "Done").locator(".dropzone");
    await dragCardTo(page, dependentCard, doneZone);
    await expect(card(columnByName(page, "Done"), dependent)).toBeVisible();

    // The soft warning surfaces in the UI banner.
    const warning = page.locator(".warnings[role='status']");
    await expect(warning).toBeVisible();
    await expect(warning).toContainText(dependency);
    await expect(warning).toContainText("is not in a done column");
  });
});
