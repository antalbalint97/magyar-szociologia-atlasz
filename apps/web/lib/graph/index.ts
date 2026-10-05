import "server-only";
import { readFileSync } from "node:fs";
import path from "node:path";
import { FileStore } from "./fileStore.ts";
import { Neo4jStore } from "./neo4jStore.ts";
import type { GraphStore } from "./types.ts";

let store: GraphStore | null = null;

export function graph(): GraphStore {
  if (store) return store;
  if (process.env.GRAPH_BACKEND === "neo4j") {
    store = new Neo4jStore();
  } else {
    store = new FileStore(releaseDir());
  }
  return store;
}

// A deployment configured with ATLAS_RELEASE_URL serves exactly the release its build fetched
// (scripts/fetch-release.mjs) and fails loudly without it: it never falls back to the fixture.
function releaseDir(): string {
  if (process.env.ATLAS_RELEASE_URL) {
    const fetched = path.join(/*turbopackIgnore: true*/ process.cwd(), ".release");
    let active: string;
    try {
      active = readFileSync(path.join(/*turbopackIgnore: true*/ fetched, "ACTIVE"), "utf8").trim();
    } catch {
      throw new Error("ATLAS_RELEASE_URL is set but no release was fetched at build time (.release/ACTIVE missing)");
    }
    return path.join(/*turbopackIgnore: true*/ fetched, active);
  }
  const release = process.env.GRAPH_RELEASE ?? "fixture-sample";
  const root = process.env.GRAPH_RELEASES_DIR ?? path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "..", "data", "releases");
  return path.join(/*turbopackIgnore: true*/ root, release);
}

export type * from "./types.ts";
