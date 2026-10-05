import type { NextConfig } from "next";

const config: NextConfig = {
  // The file backend reads the canonical release from the repository's data/ directory.
  outputFileTracingRoot: new URL("../..", import.meta.url).pathname,
  // hosted builds: the release fetched by scripts/fetch-release.mjs ships with every server route
  outputFileTracingIncludes: { "*": ["./.release/**/*"] },
  // pilot deployment: ask search engines not to index any response (also robots.ts and page metadata)
  async headers() {
    return [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
  },
  // do not write AGENTS.md / CLAUDE.md into the app directory on `next dev`
  agentRules: false,
};

export default config;
