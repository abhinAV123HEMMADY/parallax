/**
 * Extension build. esbuild directly rather than Vite or a CRX plugin, because MV3 has hard
 * output-shape requirements that a general web bundler fights:
 *
 *   - A content script cannot be an ES module. Chrome injects it as a classic script, so any
 *     `import` in the emitted file is a runtime syntax error. It must be a single IIFE bundle.
 *   - The service worker CAN be a module (manifest says "type": "module"), and wants to stay
 *     one so it can use top-level await.
 *
 * Bundling each entry with its own format is two lines here and a fight with code-splitting
 * anywhere else, so this stays a script.
 */
import { build, context } from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";

const watch = process.argv.includes("--watch");
const outdir = "dist";

await rm(outdir, { recursive: true, force: true });
await mkdir(outdir, { recursive: true });

const common = {
  bundle: true,
  target: "chrome120",
  sourcemap: watch ? "inline" : false,
  minify: !watch,
  logLevel: "info",
};

const builds = [
  // IIFE: injected as a classic script (see above).
  { ...common, entryPoints: { content: "src/content/index.ts" }, outdir, format: "iife" },
  // ESM: declared as "type": "module" in the manifest.
  { ...common, entryPoints: { background: "src/background.ts" }, outdir, format: "esm" },
  { ...common, entryPoints: { popup: "src/popup/popup.ts" }, outdir, format: "esm" },
  { ...common, entryPoints: { options: "src/options/options.ts" }, outdir, format: "esm" },
];

async function copyStatic() {
  await cp("manifest.json", `${outdir}/manifest.json`);
  await cp("src/popup/popup.html", `${outdir}/popup.html`);
  await cp("src/options/options.html", `${outdir}/options.html`);
  await cp("src/icons", `${outdir}/icons`, { recursive: true });
}

if (watch) {
  for (const options of builds) {
    const ctx = await context(options);
    await ctx.watch();
  }
  await copyStatic();
  console.log("watching…");
} else {
  await Promise.all(builds.map(build));
  await copyStatic();
  console.log(`built -> ${outdir}/`);
}
