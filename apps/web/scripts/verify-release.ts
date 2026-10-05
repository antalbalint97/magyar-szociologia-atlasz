// Opens a release with the application's FileStore and prints the canonical counts, so a
// deployment log shows which data it serves. Run by scripts/fetch-release.mjs; any thrown error
// stops the build. The FileStore is lenient (an unreadable JSONL file reads as empty), so every
// file is first parsed strictly and its row count compared with the release's own manifest.
import { readFileSync } from "node:fs";
import path from "node:path";
import { Atlas } from "../lib/atlas/atlas.ts";
import { FileStore } from "../lib/graph/fileStore.ts";

const dir = process.argv[2];
const manifest = JSON.parse(readFileSync(path.join(dir, "manifest.json"), "utf8"));

function rows(rel: string): number {
  let text: string;
  try {
    text = readFileSync(path.join(dir, rel), "utf8");
  } catch {
    throw new Error(`${rel} is missing`);
  }
  let n = 0;
  text.split("\n").forEach((line, i) => {
    if (!line.trim()) return;
    try {
      JSON.parse(line);
    } catch {
      throw new Error(`${rel} line ${i + 1} is not valid JSON`);
    }
    n++;
  });
  return n;
}

function expect(rel: string, want: unknown) {
  if (typeof want !== "number") throw new Error(`manifest has no count for ${rel}`);
  const got = rows(rel);
  if (got !== want) throw new Error(`${rel} has ${got} rows, the manifest says ${want}`);
}

const entities: Record<string, number> = manifest.entities ?? {};
if (!entities.Person) throw new Error("manifest lists no Person entities");
for (const [type, n] of Object.entries(entities)) expect(path.join("entities", `${type}.jsonl`), n);
const relations = Object.values<number>(manifest.relations ?? {}).reduce((s, n) => s + n, 0);
expect("relations.jsonl", relations || undefined);
expect("claims.jsonl", manifest.claims);
expect("documents.jsonl", manifest.documents);
try {
  JSON.parse(readFileSync(path.join(dir, "coverage.json"), "utf8"));
} catch {
  throw new Error("coverage.json is missing or not valid JSON");
}

const snap = await new FileStore(dir).snapshot();
const a = new Atlas(snap);
const count = (k: Parameters<Atlas["ofKind"]>[0]) => a.ofKind(k).length;
const persons = count("person");
console.log(`[atlas release] ${snap.info.releaseId} (${snap.info.kind}), sources: ${snap.info.sources.join(", ")}`);
console.log(`[atlas release] canonical: ${persons} persons, ${count("project")} projects, ${count("unit")} units, ` +
  `${count("topic")} topics, ${count("method")} methods; ${a.edges.length} relations; ${snap.mentions.length} mentions; ` +
  `${manifest.claims} claims from ${manifest.documents} documents (all files match the manifest)`);
if (snap.info.kind !== "snapshot") throw new Error(`release kind is ${snap.info.kind}, not snapshot`);
if (persons !== entities.Person) throw new Error(`FileStore read ${persons} persons, the manifest says ${entities.Person}`);
