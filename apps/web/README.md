# Magyar Szociológia Atlasz — web (apps/web)

Public, Hungarian-first explorer over one canonical release: researcher, project, institution,
topic and method pages, a network explorer, global search and a coverage page. Every number
and name comes from the configured release; unresolved mentions are shown as mentions, never
as researchers or projects, and every relation opens its source evidence.

```bash
cd apps/web
npm install
cp .env.example .env.local          # GRAPH_BACKEND=file reads data/releases/fixture-sample
npm run dev                          # http://localhost:3000
npm test                             # node --test: search scoring, mentions, atlas views
npm run typecheck && npm run build
```

To browse a real snapshot, extract it outside git and point the file backend at it:

```bash
GRAPH_RELEASES_DIR=/path/to/releases   # directory that contains the release folder
GRAPH_RELEASE=2026-10-tk-m2-p16        # folder name (manifest.json, entities/, relations.jsonl, coverage.json)
```

Pages read the release at request time, so the same build serves any release. A release
without `coverage.json` (e.g. the fixture) renders the coverage page with an explicit notice.

## Hosted deployment (Vercel) with a real release

Releases are not in git. A hosted build downloads one release tarball at build time
(`scripts/fetch-release.mjs`, run as `prebuild`), checks it, and ships it with the server routes.

| Vercel setting | Value |
|---|---|
| Root Directory | `apps/web` |
| Build Command | default (`npm run build`; `prebuild` fetches the release) |
| `ATLAS_RELEASE_URL` | tarball URL, e.g. a GitHub Release asset `https://github.com/<owner>/<repo>/releases/download/<tag>/<file>.tar.gz` |
| `GRAPH_RELEASE` | release id = the tarball's top directory, e.g. `2026-10-tk-m2-p31` (optional, checked when set) |
| `ATLAS_RELEASE_SHA256` | sha256 of the tarball (optional, recommended: pins the exact artifact) |

On Vercel (`VERCEL=1`) a build without `ATLAS_RELEASE_URL` stops as well (`ATLAS_ALLOW_FIXTURE=1`
deploys the fixture deliberately). Node 22.6+ is required (`engines`), for `--experimental-strip-types`.
With `ATLAS_RELEASE_URL` set the build stops, instead of falling back to the fixture, when the download
fails, the archive does not extract, `manifest.json` is missing, its `release_id` differs from
`GRAPH_RELEASE`, `dataset_kind` is not `snapshot`, the sha256 differs, or the application's
`FileStore` cannot open the release or finds no canonical persons. The build log prints the release
id, its sources and canonical counts. At runtime such a deployment reads only `.release/<id>`.
`.release/` is deleted and refetched on every build, so changing `ATLAS_RELEASE_URL` (and redeploying)
serves the new release; nothing is reused from the build cache.

Every response carries `X-Robots-Tag: noindex, nofollow`, pages carry a `robots` noindex meta tag,
and `/robots.txt` disallows everything: a pilot deployment is not for search engines. Access control
is Vercel's Deployment Protection (dashboard setting), not application code.

## Routes

| Route | What it shows |
|---|---|
| `/` | live counts, featured slices, how to read the graph |
| `/explore`, `/search?q=` | entry points and global search (canonical hits before open mentions) |
| `/people`, `/projects`, `/institutions`, `/topics` | filterable directories |
| `/person/[id]`, `/project/[id]`, `/institution/[id]` | profiles with ego network and evidence |
| `/topic/[id]`, `/method/[id]` | derived (keyword-rule) topic and method pages |
| `/network` | network explorer: presets, focus (`?focus=`), custom slice, client filters |
| `/about/data` | coverage, denominators and known blind spots, read from `coverage.json` |
| `/entity/[id]` | a Person/Project mention; canonical ids redirect to their typed route |
| `/api/search`, `/api/evidence` | JSON for the search box and the "why this relation?" panel |

## Code

- `lib/graph/`: `GraphStore` backends. `FileStore` reads a release directory; `Neo4jStore`
  queries Neo4j from server code only (`server-only`; its `snapshot()` is untested, see #30).
- `lib/atlas/`: pure view logic over a snapshot (index, profiles, slices, layouts, search,
  coverage), unit-tested with a synthetic fixture (`testFixture.ts`).
- `components/`: `NetworkCanvas` (SVG + d3-force, deterministic layouts), `EgoNetwork`,
  `GraphExplorer`, evidence and coverage components.
