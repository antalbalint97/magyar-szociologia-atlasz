// Opens a release with the application's FileStore and prints the canonical counts, so a
// deployment log shows which data it serves. Exits non-zero if the release cannot be read or
// holds no canonical researchers. Run by scripts/fetch-release.mjs.
import { Atlas } from "../lib/atlas/atlas.ts";
import { FileStore } from "../lib/graph/fileStore.ts";

const dir = process.argv[2];
const snap = await new FileStore(dir).snapshot();
const a = new Atlas(snap);
const count = (k: Parameters<Atlas["ofKind"]>[0]) => a.ofKind(k).length;
const persons = count("person");
console.log(`[atlas release] ${snap.info.releaseId} (${snap.info.kind}), sources: ${snap.info.sources.join(", ")}`);
console.log(`[atlas release] canonical: ${persons} persons, ${count("project")} projects, ${count("unit")} units, ` +
  `${count("topic")} topics, ${count("method")} methods; ${a.edges.length} relations; ${snap.mentions.length} mentions`);
if (snap.info.kind !== "snapshot") throw new Error(`release kind is ${snap.info.kind}, not snapshot`);
if (persons === 0) throw new Error("release holds no canonical persons");
