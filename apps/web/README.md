# Web explorer (apps/web)

Minimal Next.js explorer: search, entity profile, observed vs derived relations, a small
radial ego network and the source evidence behind every field and edge.

```bash
cd apps/web
npm install
cp .env.example .env.local          # GRAPH_BACKEND=file reads data/releases/fixture-sample
npm run dev                          # http://localhost:3000
npm test                             # search scoring tests (node --test)
```

Backends (`lib/graph/`): `FileStore` reads a canonical release directly; `Neo4jStore`
queries Neo4j from server components only. Credentials stay on the server
(`lib/graph/index.ts` imports `server-only`).
