import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const COMPOSE = "docker compose -p trackeroo-e2e -f docker-compose.e2e.yml";

export default async function globalTeardown(): Promise<void> {
  if (process.env.E2E_SKIP_DOCKER) return;
  console.log("[e2e] Tearing down Docker stack…");
  execSync(`${COMPOSE} down -v --remove-orphans`, {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
}
