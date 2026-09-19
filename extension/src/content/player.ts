/**
 * Access to YouTube's player from the page.
 *
 * Deliberately not the YouTube IFrame Player API: that API exists so a *third-party page* can
 * control an embedded player across an origin boundary. A content script is already inside the
 * page, so the `<video>` element is right there — `currentTime` reads the position and assigning
 * it seeks. No API to load, nothing to wait for, and nothing to go stale on SPA navigation.
 */

/** Player selectors, in order of specificity. YouTube renders other <video> elements (previews,
 * ads, hover thumbnails), so the bare tag is a last resort rather than the first guess. */
const SELECTORS = [
  "#movie_player video.html5-main-video",
  "#movie_player video",
  "video.html5-main-video",
  "video",
];

export function getVideo(): HTMLVideoElement | null {
  for (const selector of SELECTORS) {
    const element = document.querySelector<HTMLVideoElement>(selector);
    if (element) return element;
  }
  return null;
}

export function currentSeconds(): number {
  const video = getVideo();
  return video ? Math.max(0, Math.floor(video.currentTime)) : 0;
}

export function seekTo(seconds: number): void {
  const video = getVideo();
  if (!video) return;
  video.currentTime = Math.max(0, seconds);
  // A seek from a note is a request to look at that moment, so start it playing rather than
  // leaving a paused frame the learner then has to click.
  void video.play().catch(() => {
    /* autoplay policy may refuse; the seek already happened, which is the important part */
  });
}

export function pause(): void {
  getVideo()?.pause();
}

/** The `v` query parameter. Null on any non-watch page, which is how the panel decides to unmount. */
export function currentVideoId(): string | null {
  if (!location.pathname.startsWith("/watch")) return null;
  return new URLSearchParams(location.search).get("v");
}

/**
 * The video's title. Tries the rendered heading first, then `document.title`.
 *
 * `document.title` is the fallback rather than the primary source because YouTube updates it
 * asynchronously on SPA navigation — read too early and it still says the *previous* video, which
 * would silently file notes under the wrong title.
 */
export function currentVideoTitle(): string {
  const heading = document.querySelector<HTMLElement>(
    "h1.ytd-watch-metadata yt-formatted-string, h1.title yt-formatted-string, #title h1",
  );
  const rendered = heading?.textContent?.trim();
  if (rendered) return rendered;
  return document.title.replace(/\s*-\s*YouTube\s*$/, "").trim();
}

/** The player's on-screen box, for cropping a screenshot to it. */
export function playerRect(): { x: number; y: number; width: number; height: number } | null {
  const video = getVideo();
  if (!video) return null;
  const rect = video.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return null;
  return { x: rect.left, y: rect.top, width: rect.width, height: rect.height };
}

export function formatTimestamp(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
}
