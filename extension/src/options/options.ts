/**
 * Options page: backend URL and default sharing.
 *
 * There is no profile picker. Notes go to the learner the web app also defaults to
 * (DEFAULT_LEARNER_ID), so the extension works the moment it is installed. The backend has no
 * auth either way; the page says so plainly rather than dressing the absence up as a login.
 */

import { health } from "../lib/api";
import { getSettings, saveSettings } from "../lib/storage";

const apiBaseInput = document.getElementById("apiBase") as HTMLInputElement;
const webBaseInput = document.getElementById("webBase") as HTMLInputElement;
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
  webBaseInput.value = settings.webBase;
  shareBox.checked = settings.shareByDefault;

  await checkReachable();

  apiBaseInput.addEventListener("change", async () => {
    await saveSettings({ apiBase: apiBaseInput.value.trim().replace(/\/$/, "") });
    await checkReachable();
  });

  document.getElementById("save")?.addEventListener("click", async () => {
    await saveSettings({
      apiBase: apiBaseInput.value.trim().replace(/\/$/, ""),
      webBase: webBaseInput.value.trim().replace(/\/$/, ""),
      shareByDefault: shareBox.checked,
    });
    savedLabel.textContent = "Saved.";
    setTimeout(() => {
      savedLabel.textContent = "";
    }, 2000);
  });
}

void main();
