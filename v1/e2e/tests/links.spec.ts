import { test, expect, addTaskViaBoard, openTask } from "../helpers/app";

test.describe("Links", () => {
  test("adds a PR link that renders as a clickable anchor", async ({ page }) => {
    await page.goto("/");
    const title = `Task with PR ${Date.now()}`;
    await addTaskViaBoard(page, "Backlog", title);
    const panel = await openTask(page, title);

    const url = "https://github.com/acme/trackeroo/pull/42";
    const linkSection = panel.locator("section").filter({ hasText: "Links" });
    await linkSection.getByPlaceholder("https://").fill(url);
    await linkSection.getByPlaceholder("Label").fill("PR #42");
    await linkSection.locator("select").selectOption("pr");
    await linkSection.getByRole("button", { name: "Add link" }).click();

    const anchor = linkSection.locator(".link-list a");
    await expect(anchor).toHaveAttribute("href", url);
    await expect(anchor).toHaveText("PR #42");
    await expect(linkSection.locator(".link-type")).toHaveText("pr");
  });
});
