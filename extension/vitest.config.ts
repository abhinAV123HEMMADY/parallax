import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // jsdom, not node: captions.ts uses DOMParser to read YouTube's XML timedtext format, and
    // that is browser API surface the tests exercise for real rather than mock.
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
});
