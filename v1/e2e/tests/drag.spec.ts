import {
  test,
  expect,
  columnByName,
  card,
  addTaskViaBoard,
} from "../helpers/app";
import { dragCardTo } from "../helpers/dnd";

test.describe("Drag and drop", () => {
  test("@smoke drags a task across swimlanes and persists after reload", async ({
    page,
  }) => {
    await page.goto("/");
    const title = `Draggable ${Date.now()}`;
    await addTaskViaBoard(page, "Backlog", title);

    const theCard = card(columnByName(page, "Backlog"), title);
    const target = columnByName(page, "In Progress").locator(".dropzone");
    await dragCardTo(page, theCard, target);

    // Landed in the target column, gone from the source.
    await expect(card(columnByName(page, "In Progress"), title)).toBeVisible();
    await expect(card(columnByName(page, "Backlog"), title)).toHaveCount(0);

    // Persists across a full reload (proves the /move API + DB write).
    await page.reload();
    await expect(card(columnByName(page, "In Progress"), title)).toBeVisible();
    await expect(card(columnByName(page, "Backlog"), title)).toHaveCount(0);
  });
});
