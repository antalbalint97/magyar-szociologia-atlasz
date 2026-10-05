import assert from "node:assert/strict";
import { test } from "node:test";
import { isDeferred } from "../graph/mentions.ts";
import { Atlas } from "./atlas.ts";
import { coverageView } from "./coverage.ts";
import { coveredUnits } from "./directory.ts";
import { forceLayout, packPositions, radialLayout, unpackPositions } from "./layout.ts";
import { assemble, buildSlice, filterSlice, focusSpec, restrictSlice, sliceStats } from "./network.ts";
import { personProfile, projectProfile } from "./profiles.ts";
import { searchAtlas } from "./search.ts";
import { fixtureSnapshot } from "./testFixture.ts";
import { STATUS_SHORT, hrefFor, percent } from "./vocab.ts";

const a = new Atlas(fixtureSnapshot());

test("only canonical entities become nodes; mentions and dangling relations do not", () => {
  assert.equal(a.ofKind("person").length, 3);
  for (const m of a.mentions) assert.equal(a.node(m.id), undefined);
  assert.equal(a.edges.some((e) => e.source === "per_x"), false);
  assert.deepEqual(a.projectPeople("prj_1").sort(), ["per_1", "per_2", "per_3"]);
});

test("taxonomy terms show the Hungarian label and keep the canonical one", () => {
  const t = a.node("top_1")!;
  assert.equal(t.label, "Romakutatás");
  assert.equal(t.altLabel, "Roma studies");
});

test("project titles are never translated", () => {
  assert.equal(a.node("prj_1")!.label, "Közös projekt");
  assert.equal(a.node("prj_1")!.altLabel, null);
});

test("search ranks every canonical hit before mention hits and folds accents", () => {
  const hits = searchAtlas(a, "alfa");
  const firstMention = hits.findIndex((h) => h.mention);
  assert.ok(firstMention > 0);
  assert.ok(hits.slice(firstMention).every((h) => h.mention));
  assert.equal(hits[0].id, "per_1");
  assert.equal(hits[0].href, "/person/per_1");
  // resolved mentions are not offered: they are the person
  assert.equal(hits.some((h) => h.id === "pmn_1"), false);
  assert.equal(searchAtlas(a, "beta bela")[0]?.id, "per_2");
  assert.equal(searchAtlas(a, "romakutatas")[0]?.id, "top_1");
});

test("unresolved mention hits are deduplicated by stated name and routed to the mention view", () => {
  const hits = searchAtlas(a, "Delta Dóra");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].mention, true);
  assert.equal(hits[0].type, "PersonMention");
  assert.match(hits[0].href, /^\/entity\/pmn_/);
});

test("entity routes follow the entity type", () => {
  assert.equal(hrefFor("per_1", "Person"), "/person/per_1");
  assert.equal(hrefFor("prj_1", "Project"), "/project/prj_1");
  assert.equal(hrefFor("ou_a1", "OrganisationalUnit"), "/institution/ou_a1");
  assert.equal(hrefFor("org_a", "Institution"), "/institution/org_a");
  assert.equal(hrefFor("top_1", "ResearchTopic"), "/topic/top_1");
  assert.equal(hrefFor("met_1", "Method"), "/method/met_1");
  assert.equal(hrefFor("pmn_2", "PersonMention"), "/entity/pmn_2");
  assert.equal(hrefFor("x", "Unknown"), "/entity/x");
});

test("observed and derived relations keep distinct labels", () => {
  assert.notEqual(STATUS_SHORT.OBSERVED, STATUS_SHORT.DERIVED);
});

test("a deferred mention (#9) is open, not a project relation", () => {
  const m = a.mentionById.get("pjm_2")!;
  assert.equal(isDeferred(m), true);
  assert.equal(isDeferred(a.mentionById.get("pjm_1")!), false);
  const p = personProfile(a, "per_2")!;
  assert.equal(p.deferredProjects.length, 1);
  assert.equal(p.led.length + p.participated.length, 1);
  assert.equal(p.unresolvedProjects.length, 0);
});

test("person profile groups projects and keeps unresolved profile projects apart", () => {
  const p = personProfile(a, "per_1")!;
  assert.deepEqual(p.led.map((r) => r.project.id), ["prj_1"]);
  assert.equal(p.participated.length, 0); // the parallel participation edge is the same project
  assert.equal(p.unresolvedProjects.length, 1);
  assert.equal(p.topics.length, 1);
  assert.deepEqual(p.coParticipants.map((c) => c.person.id), ["per_2", "per_3"]);
  assert.equal(personProfile(a, "prj_1"), null);
});

test("project profile reports size as distinct canonical people", () => {
  const p = projectProfile(a, "prj_1")!;
  assert.equal(a.projectSize("prj_1"), 3);
  assert.ok(p);
});

test("registry-only units are recognised and not listed as covered", () => {
  assert.equal(a.isRegistryOnly("org_r"), true);
  assert.equal(a.isRegistryOnly("org_a"), false);
  assert.equal(coveredUnits(a).some((u) => u.id === "org_r"), false);
});

test("assemble merges parallel relations into one edge that keeps every relation", () => {
  const s = buildSlice(a, focusSpec(a, "per_1")!);
  const e = s.edges.find((x) => x.source === "per_1" && x.target === "prj_1")!;
  assert.equal(e.relationIds.length, 2);
  assert.equal(e.group, "lead");
  assert.deepEqual(e.types.sort(), ["PARTICIPATES_IN", "PRINCIPAL_INVESTIGATOR_OF"]);
  const topic = s.edges.find((x) => x.target === "top_1")!;
  assert.equal(topic.status, "DERIVED");
  assert.deepEqual(s.seeds, ["per_1"]);
  assert.equal(s.nodes.find((n) => n.id === "per_1")!.hop, 0);
  assert.equal(s.nodes.find((n) => n.id === "per_2")!.hop, 2);
});

test("assemble ignores relations to nodes outside the slice", () => {
  const s = assemble(a, new Map([["per_1", 0], ["prj_1", 1]]), a.edges.map((e) => e.id), ["per_1"]);
  assert.equal(s.nodes.length, 2);
  assert.equal(s.edges.length, 1);
  assert.equal(s.nodes.find((n) => n.id === "prj_1")!.size, 3);
});

test("relation-family slices respect the unit filter", () => {
  const all = buildSlice(a, { relations: ["lead", "participation"] });
  assert.equal(all.nodes.filter((n) => n.kind === "project").length, 2);
  const b = buildSlice(a, { relations: ["lead", "participation"], unit: "org_b" });
  // only edges touching the unit's own people: the shared project appears, its other members do not
  assert.deepEqual(b.nodes.filter((n) => n.kind === "person").map((n) => n.id), ["per_2"]);
  assert.ok(b.nodes.some((n) => n.id === "prj_1"));
  assert.equal(b.nodes.some((n) => n.id === "prj_2"), false);
});

test("filterSlice keeps seeds, drops isolated nodes and filters derived relations", () => {
  const s = buildSlice(a, focusSpec(a, "per_1")!);
  const observed = filterSlice(s, { statuses: ["OBSERVED"] });
  assert.equal(observed.edges.some((e) => e.status !== "OBSERVED"), false);
  assert.equal(observed.nodes.some((n) => n.id === "top_1"), false);
  const noProjects = filterSlice(s, { kinds: ["unit"] });
  assert.ok(noProjects.nodes.some((n) => n.id === "per_1"));
  assert.equal(noProjects.nodes.some((n) => n.kind === "project"), false);
  const small = filterSlice(s, { maxProjectSize: 2 });
  assert.equal(small.nodes.some((n) => n.id === "prj_1"), false);
  const st = sliceStats(s);
  assert.equal(st.observed + st.derived, st.edges);
});

test("restrictSlice recomputes degrees from the kept edges", () => {
  const s = buildSlice(a, focusSpec(a, "per_1")!);
  const r = restrictSlice(s, new Set(["per_1", "prj_1", "per_2"]));
  assert.equal(r.nodes.find((n) => n.id === "prj_1")!.degree, 2);
  assert.equal(r.edges.length, 2);
});

test("layouts are deterministic and survive packing", () => {
  const s = buildSlice(a, { relations: ["lead", "participation", "affiliation"] });
  const p1 = forceLayout(s.nodes, s.edges, { cluster: true });
  const p2 = forceLayout([...s.nodes].reverse(), s.edges, { cluster: true });
  assert.deepEqual([...p1.entries()].sort(), [...p2.entries()].sort());
  const round = unpackPositions(packPositions(p1));
  for (const [id, p] of p1) assert.ok(Math.abs(round.get(id)!.x - p.x) < 0.5);
  const ego = buildSlice(a, focusSpec(a, "per_1")!);
  const r = radialLayout(ego.nodes, ego.edges, "per_1");
  assert.deepEqual(r.get("per_1"), { x: 0, y: 0, anchor: "middle" });
  assert.deepEqual(r, radialLayout(ego.nodes, ego.edges, "per_1"));
});

test("percent rounds half up and refuses an empty denominator", () => {
  assert.equal(percent(1, 8), "13%"); // 12.5
  assert.equal(percent(450, 783), "57%");
  assert.equal(percent(0, 0), "–");
});

test("coverage view keeps numerators with denominators and tolerates a missing report", () => {
  const empty = coverageView({ coverage: null, manifest: { release_id: "x", sources: ["SRC_A"] } });
  assert.equal(empty.available, false);
  assert.equal(empty.personMentionsAll, null);
  assert.equal(empty.sources.length, 1);
  const v = coverageView({
    manifest: { release_id: "r" },
    coverage: {
      canonicalization: {
        person_mentions: { by_source: { all: { total: 10, resolved: 7 }, SRC_A: { total: 10, resolved: 7, UNRESOLVED: 3, DETERMINISTIC: 7 } } },
        project_mentions: { by_source: {}, unresolved_by_category: { all: { no_candidate: 4 } } },
      },
    },
  });
  assert.deepEqual(v.personMentionsAll, { n: 7, of: 10 });
  assert.deepEqual(v.personMentions[0].value, { n: 7, of: 10 });
  assert.equal(v.personMentions[0].parts!.reduce((s, p) => s + p.n, 0), 10);
  assert.equal(v.unresolvedProjectReasons[0].n, 4);
});
