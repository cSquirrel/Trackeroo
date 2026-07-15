// Auto-update controller (Svelte 5 runes). Wraps the Tauri updater/process
// plugins so the UI can check for, download, install, and relaunch into a new
// release. One shared instance drives both the passive banner and the manual
// "Check for updates" buttons.
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type Update } from "@tauri-apps/plugin-updater";

// idle:        nothing to show
// checking:    a check is in flight
// available:   a newer release was found and is offered
// downloading: the update bundle is streaming down
// installing:  bytes are being swapped in; relaunch is imminent
// uptodate:    the last (manual) check found no newer release
// error:       the last check/install failed
type Phase =
  | "idle"
  | "checking"
  | "available"
  | "downloading"
  | "installing"
  | "uptodate"
  | "error";

// `tauri dev` has no installed bundle to replace, so the updater can't work
// there; surface that instead of throwing a confusing runtime error. A release
// build (vite build) flips this to false so real checks run.
const DEV_BUILD = import.meta.env.DEV;

class UpdateController {
  phase = $state<Phase>("idle");
  // The offered update's version + notes (set once phase === "available").
  newVersion = $state<string | null>(null);
  notes = $state<string | null>(null);
  error = $state<string | null>(null);
  // Download progress in bytes; total is 0 until the server reports a length.
  downloaded = $state(0);
  total = $state(0);
  // True when the current check was user-initiated, so we only show the
  // "you're up to date" / error confirmations for explicit checks — a silent
  // launch check that finds nothing stays invisible.
  manual = $state(false);

  #update: Update | null = null;
  #busy = false;

  get isDevBuild(): boolean {
    return DEV_BUILD;
  }

  async currentVersion(): Promise<string> {
    return getVersion();
  }

  // Check for a newer release. `manual` = triggered by a user click (surfaces
  // "up to date" and errors); otherwise a silent background check.
  async runCheck(manual = false): Promise<void> {
    if (this.#busy) return;
    if (DEV_BUILD) {
      if (manual) {
        this.manual = true;
        this.phase = "uptodate";
      }
      return;
    }
    this.#busy = true;
    this.manual = manual;
    this.error = null;
    // Don't clobber an in-progress download/install with a stray check.
    if (this.phase === "idle" || this.phase === "uptodate" || this.phase === "error") {
      this.phase = "checking";
    }
    try {
      const update = await check();
      if (update) {
        this.#update = update;
        this.newVersion = update.version;
        this.notes = update.body ?? null;
        this.phase = "available";
      } else {
        this.phase = "uptodate";
      }
    } catch (e) {
      this.phase = "error";
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.#busy = false;
    }
  }

  // Download the offered update, install it, and relaunch into it. On success
  // the process is replaced, so this never returns normally.
  async downloadAndInstall(): Promise<void> {
    if (!this.#update) return;
    // Installing is always an explicit user action ("Update & restart"), so its
    // progress and any failure must be visible even if the update was found by
    // a silent launch check (manual === false until now).
    this.manual = true;
    this.error = null;
    this.downloaded = 0;
    this.total = 0;
    this.phase = "downloading";
    try {
      await this.#update.downloadAndInstall((event) => {
        switch (event.event) {
          case "Started":
            this.total = event.data.contentLength ?? 0;
            break;
          case "Progress":
            this.downloaded += event.data.chunkLength;
            break;
          case "Finished":
            this.phase = "installing";
            break;
        }
      });
      await relaunch();
    } catch (e) {
      this.phase = "error";
      this.error = e instanceof Error ? e.message : String(e);
    }
  }

  // Hide a terminal banner (available / up-to-date / error). No-op mid-flight.
  dismiss(): void {
    if (this.phase === "available" || this.phase === "uptodate" || this.phase === "error") {
      this.phase = "idle";
      this.manual = false;
      this.error = null;
    }
  }
}

export const updater = new UpdateController();
