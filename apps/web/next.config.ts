import type { NextConfig } from "next";

const config: NextConfig = {
  // The file backend reads the canonical release from the repository's data/ directory.
  outputFileTracingRoot: new URL("../..", import.meta.url).pathname,
  // do not write AGENTS.md / CLAUDE.md into the app directory on `next dev`
  agentRules: false,
};

export default config;
