# Repository audit (deliverable A), 2026-10-04

## What existed

The only candidate in the account was `antalbalint97/elte-tk-discovery` (private, last
push 2026-10-02). Despite its name, it is a reverse-engineering kit for the AskAI
**Bifrost** LLM gateway (dashboard CSV parsing, request-log forensics, provider/latency
analysis, host topology scripts). Stack: plain Python scripts + CSV, no package, no
tests, no scraping of institutional pages, no data model, no graph or frontend.

Nothing else in the account relates to Hungarian sociology or academic graphs
(`ksh_public_data` is KSH statistics, not people or institutions).

## Reusable

* Conventions worth keeping: read-only/ethics "ground rules" table in its README, env-var
  secrets, `.gitignore` for data/outputs. These were adopted here in spirit.
* No code was reusable for this project.

## Missing (everything this project needs)

Source registry, polite fetcher with raw snapshots, adapters, typed schemas, provenance
model, entity resolution, canonical dataset, QA, graph import, frontend, docs, tests.

## Decision

Separate repository: `magyar-szociologia-atlasz`. Mixing a sociology knowledge graph into
an LLM-gateway forensics repo would confuse both and make a future public release of
this project (likely) awkward next to a private infrastructure-forensics kit.

Note for the owner: `elte-tk-discovery/bifrost_research/` contains committed files
named `bilbo_key.json` and `vllm_keys.json`. They were not opened during the audit; if
they contain live credentials they should be rotated and removed from history.

## Environment constraints found

The build environment could not reach any `*.tk.elte.hu`, `tarki.hu`, `krtk.hu` or
registry host over HTTP (egress policy allows only package registries). Site structure
was inspected through a text-rendering web reader, which is enough to design adapters
but not to capture raw HTML. Consequences are documented in
docs/uncertainties_and_next_steps.md.
