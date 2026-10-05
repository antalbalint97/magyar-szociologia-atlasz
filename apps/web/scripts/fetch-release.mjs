// Build step for hosted deployments (Vercel). Releases live outside git, so a deployment
// names its release by configuration:
//   ATLAS_RELEASE_URL     tarball URL (or local path) of one canonical release, e.g. a GitHub Release asset
//   GRAPH_RELEASE         expected release id = the tarball's top-level directory (optional; taken from the archive if unset)
//   ATLAS_RELEASE_SHA256  expected sha256 of the tarball (optional, recommended)
// The release is extracted into .release/<id>/ and .release/ACTIVE names it; next.config.ts ships
// .release/ with the server routes, and lib/graph/index.ts reads only that release.
// Every failure stops the build: a deployment configured for a real release never falls back to
// the fixture. Without ATLAS_RELEASE_URL this step does nothing (local dev and CI keep data/releases).
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const fail = (msg) => {
  console.error(`\n[atlas release] BUILD STOPPED: ${msg}\n`);
  process.exit(1);
};

const src = process.env.ATLAS_RELEASE_URL?.trim();
if (!src) {
  console.log("[atlas release] ATLAS_RELEASE_URL not set: no release fetched (local/CI default data/releases)");
  process.exit(0);
}

const dir = path.join(process.cwd(), ".release");
rmSync(dir, { recursive: true, force: true }); // never reuse a release from an earlier build or cache
mkdirSync(dir, { recursive: true });

let bytes;
if (/^https?:\/\//.test(src)) {
  let res;
  try {
    res = await fetch(src, { redirect: "follow" });
  } catch (e) {
    fail(`download failed: ${src} (${e.message})`);
  }
  if (!res.ok) fail(`download failed: HTTP ${res.status} for ${src}`);
  bytes = Buffer.from(await res.arrayBuffer());
} else {
  if (!existsSync(src)) fail(`release archive not found: ${src}`);
  bytes = readFileSync(src);
}
if (bytes.length < 1024) fail(`download is ${bytes.length} bytes, not a release archive: ${src}`);
const sha = createHash("sha256").update(bytes).digest("hex");
const want = process.env.ATLAS_RELEASE_SHA256?.trim().toLowerCase();
if (want && want !== sha) fail(`sha256 mismatch: expected ${want}, got ${sha}`);

const archive = path.join(dir, "release.tar.gz");
writeFileSync(archive, bytes);
try {
  execFileSync("tar", ["-xzf", archive, "-C", dir], { stdio: "inherit" });
} catch {
  fail(`extraction failed for ${src}`);
}
rmSync(archive);

const tops = readdirSync(dir).filter((d) => statSync(path.join(dir, d)).isDirectory());
const release = process.env.GRAPH_RELEASE?.trim() || (tops.length === 1 ? tops[0] : "");
if (!release) fail(`GRAPH_RELEASE not set and the archive has ${tops.length} top-level directories (${tops.join(", ")})`);
if (!tops.includes(release)) fail(`release "${release}" not in the archive (contains: ${tops.join(", ") || "nothing"})`);
const manifestPath = path.join(dir, release, "manifest.json");
if (!existsSync(manifestPath)) fail(`${release}/manifest.json missing in the archive`);
let manifest;
try {
  manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
} catch (e) {
  fail(`${release}/manifest.json is not valid JSON (${e.message})`);
}
if (manifest.release_id !== release) fail(`manifest release_id "${manifest.release_id}" does not match "${release}"`);
if (manifest.dataset_kind !== "snapshot") fail(`dataset_kind is "${manifest.dataset_kind}", expected "snapshot" (fixtures are not deployed)`);
if (!Array.isArray(manifest.sources) || !manifest.sources.length) fail("manifest lists no sources");
writeFileSync(path.join(dir, "ACTIVE"), release);

// open it with the application's own FileStore and report what it holds
try {
  execFileSync(process.execPath, ["--experimental-strip-types", "--no-warnings", path.join("scripts", "verify-release.ts"), path.join(dir, release)], { stdio: "inherit" });
} catch {
  fail(`the FileStore could not open ${release} (see above)`);
}
console.log(`[atlas release] ${release} from ${src} (sha256 ${sha})`);
