# ADR-0005: No separate API service in phase 1

Status: accepted (2026-10-04)

Decision: Next.js server components / route handlers query the graph store directly;
credentials never reach the browser. A FastAPI service is introduced only for a public
research API with external consumers, heavy analytical endpoints, authenticated editing,
or scheduled jobs the CLI cannot cover.
