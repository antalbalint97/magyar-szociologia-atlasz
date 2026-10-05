import "server-only";
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
    const release = process.env.GRAPH_RELEASE ?? "fixture-sample";
    const root = process.env.GRAPH_RELEASES_DIR ?? path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "..", "data", "releases");
    store = new FileStore(path.join(/*turbopackIgnore: true*/ root, release));
  }
  return store;
}

export type * from "./types.ts";
