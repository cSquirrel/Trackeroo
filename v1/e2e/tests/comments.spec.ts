import {
  test,
  expect,
  addTaskViaBoard,
  openTask,
  setAuthor,
} from "../helpers/app";

test.describe("Comments and annotations", () => {
  test("@smoke adds a comment and an annotation", async ({ page }) => {
    await page.goto("/");
    await setAuthor(page, "Tester");

    const title = `Task with notes ${Date.now()}`;
    await addTaskViaBoard(page, "Backlog", title);
    const panel = await openTask(page, title);

    const commentBox = panel.getByPlaceholder("Write a comment");
    const addComment = panel.locator(".comment-actions button");

    const comments = panel.locator(".comment-list .comment");

    // A plain comment. Wait for it to land before adding the next — the submit
    // handler clears the textarea asynchronously after the request resolves.
    await commentBox.fill("This is a plain comment");
    await addComment.click();
    await expect(comments).toHaveCount(1);

    // An annotation, via the kind toggle.
    await commentBox.fill("This is an annotation");
    await panel.locator('.kind-toggle input[type="checkbox"]').check();
    await addComment.click();

    await expect(comments).toHaveCount(2);
    await expect(
      panel.locator(".comment", { hasText: "This is a plain comment" }),
    ).toBeVisible();

    const annotation = panel.locator(".comment.annotation", {
      hasText: "This is an annotation",
    });
    await expect(annotation).toBeVisible();
    await expect(annotation.locator(".kind-pill")).toHaveText("annotation");
  });
});
