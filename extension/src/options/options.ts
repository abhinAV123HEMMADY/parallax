/**
 * Options page: backend URL, learner profile, default sharing.
 *
 * The learner picker exists because the backend has no auth — app/api/routes_users.py lists
 * profiles and nothing gates them. That is honest for a local project and stated plainly in the
 * page itself rather than dressed up as a login.
 */

import { health, listUsers } from "../lib/api";
import { getSettings, saveSettings } from "../lib/storage";

const apiBaseInput = document.getElementById("apiBase") as HTMLInputElement;
const learnerSelect = document.getElementById("learner") as HTMLSelectElement;
const shareBox = document.getElementById("share") as HTMLInputElement;
const savedLabel = document.getElementById("saved") as HTMLSpanElement;
const reachLine = document.getElementById("reach") as HTMLParagraphElement;
const corsLine = document.getElementById("cors") as HTMLParagraphElement;

/**
 * The extension's own origin, which is what the backend's CORS_ORIGINS has to contain. Shown here
 * because an unpacked extension gets a fresh id on every reload unless the manifest pins a key,
 * so this value changes and is otherwise annoying to find.
 */
function showCorsHint(): void {
  corsLine.innerHTML =
    `Add this origin to <code>CORS_ORIGINS</code> in your backend <code>.env</code>: ` +
    `<code>chrome-extension://${chrome.runtime.id}</code>. Unpacked extensions get a new id on ` +
    `each reload unless the manifest pins a <code>key</code>, so re-check this after reloading.`;
}

async function loadLearners(selected: string | null): Promise<void> {
  try {
    const users = await listUsers();
    learnerSelect.replaceChildren();

    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "— select —";
    learnerSelect.append(blank);

    for (const user of users) {
      const option = document.createElement("option");
      option.value = user.id;
      option.textContent = user.grade_level ? `${user.name} (${user.grade_level})` : user.name;
      if (user.id === selected) option.selected = true;
      learnerSelect.append(option);
    }
  } catch (error) {
    learnerSelect.replaceChildren();
    const failed = document.createElement("option");
    failed.value = selected ?? "";
    failed.textContent = selected ?? "could not load profiles";
    learnerSelect.append(failed);
    reachLine.textContent = `Couldn't reach the backend: ${
      error instanceof Error ? error.message : String(error)
    }`;
    reachLine.className = "error";
  }
}

async function checkReachable(): Promise<void> {
  try {
    const info = await health();
    reachLine.textContent = `Reachable · embeddings: ${info.embed_backend} · model: ${
      info.llm_configured ? "live" : "stub (placeholder content)"
    }`;
    reachLine.className = "muted";
  } catch {
    reachLine.textContent = "Not reachable. Is `make backend` running?";
    reachLine.className = "error";
  }
}

async function main(): Promise<void> {
  showCorsHint();
  const settings = await getSettings();
  apiBaseInput.value = settings.apiBase;
  shareBox.checked = settings.shareByDefault;

  await checkReachable();
  await loadLearners(settings.learnerId);

  // Saving the URL before reloading profiles, so switching backends repopulates the picker from
  // the new one rather than leaving stale names selectable.
  apiBaseInput.addEventListener("change", async () => {
    await saveSettings({ apiBase: apiBaseInput.value.trim().replace(/\/$/, "") });
    await checkReachable();
    await loadLearners(learnerSelect.value || null);
  });

  document.getElementById("save")?.addEventListener("click", async () => {
    await saveSettings({
      apiBase: apiBaseInput.value.trim().replace(/\/$/, ""),
      learnerId: learnerSelect.value || null,
      shareByDefault: shareBox.checked,
    });
    savedLabel.textContent = "Saved.";
    setTimeout(() => {
      savedLabel.textContent = "";
    }, 2000);
  });
}

void main();
