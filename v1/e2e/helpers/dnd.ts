import type { Locator, Page } from "@playwright/test";

// svelte-dnd-action listens to real mouse events (not the HTML5 drag API that
// Playwright's dragTo simulates), so we drive a manual pointer gesture: press
// on the card, nudge past the drag threshold, glide to the target dropzone in
// several steps, then release.
export async function dragCardTo(
  page: Page,
  card: Locator,
  targetDropzone: Locator,
): Promise<void> {
  const from = await card.boundingBox();
  const to = await targetDropzone.boundingBox();
  if (!from || !to) throw new Error("dragCardTo: could not measure elements");

  const startX = from.x + from.width / 2;
  const startY = from.y + from.height / 2;
  // Aim near the top of the target dropzone so the card lands in that column.
  const endX = to.x + to.width / 2;
  const endY = to.y + Math.min(to.height / 2, 40);

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  // Small nudge to trip the drag-start threshold.
  await page.mouse.move(startX, startY - 12, { steps: 6 });
  await page.mouse.move(endX, endY, { steps: 30 });
  // A tiny extra move + settle lets svelte-dnd-action register the hover target.
  await page.mouse.move(endX, endY + 1, { steps: 4 });
  await page.waitForTimeout(200);
  await page.mouse.up();
}
