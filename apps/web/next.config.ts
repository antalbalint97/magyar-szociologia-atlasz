import type { NextConfig } from "next";

const config: NextConfig = {
  // The file backend reads the canonical release from the repository's data/ directory.
  outputFileTracingRoot: new URL("../..", import.meta.url).pathname,
};

export default config;
