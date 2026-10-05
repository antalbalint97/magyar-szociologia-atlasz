// The one place pages get the atlas index from. Built once per server process from the
// configured GraphStore (file backend by default), so pages never read release files themselves.
import "server-only";
import { graph } from "../graph/index.ts";
import { Atlas } from "./atlas.ts";

let cached: Promise<Atlas> | null = null;

export function atlas(): Promise<Atlas> {
  cached ??= graph().snapshot().then((s) => new Atlas(s));
  return cached;
}

export async function coverageData() {
  return graph().coverage();
}

const layouts = new Map<string, unknown>();

/** Per-process memo for deterministic, expensive derived values (e.g. preset layouts). */
export function memo<T>(key: string, fn: () => T): T {
  if (!layouts.has(key)) layouts.set(key, fn());
  return layouts.get(key) as T;
}
