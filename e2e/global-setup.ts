import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import http from "node:http";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const COMPOSE = "docker compose -p trackeroo-e2e -f docker-compose.e2e.yml";
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:8001";

function sh(cmd: string): void {
  execSync(cmd, { cwd: REPO_ROOT, stdio: "inherit" });
}

function healthy(url: string): Promise<boolean> {
  return new Promise((res) => {
    const req = http.get(`${url}/api/health`, (r) => {
      r.resume();
      res(r.statusCode === 200);
    });
    req.on("error", () => res(false));
    req.setTimeout(2000, () => {
      req.destroy();
      res(false);
    });
  });
}

async function waitForHealth(url: string, timeoutMs = 120_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await healthy(url)) return;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Backend at ${url} never became healthy`);
}

export default async function globalSetup(): Promise<void> {
  if (process.env.E2E_SKIP_DOCKER) {
    console.log(`[e2e] E2E_SKIP_DOCKER set — using existing stack at ${BASE_URL}`);
    await waitForHealth(BASE_URL);
    return;
  }

  console.log("[e2e] Booting fresh Docker stack for E2E…");
  // Wipe any prior volume so the DB re-seeds deterministically, then build+boot.
  sh(`${COMPOSE} down -v --remove-orphans`);
  sh(`${COMPOSE} up -d --build --wait`);
  await waitForHealth(BASE_URL);
  console.log(`[e2e] Stack healthy at ${BASE_URL}`);
}
