import assert from "node:assert/strict";
import { test } from "node:test";
import { RESOLVED_MENTION, toMention } from "./mentions.ts";

const row = {
  canonical_id: "pmn_1", stated_name: "Szabó Sára", source_url: "https://szociologia.tk.elte.hu/p",
  resolution: { status: "REVIEW_REQUIRED", reason: "2 viable candidates" },
  candidates: [{ person_id: "per_a", name_match: "NAME_EXACT", signals: ["NAME_EXACT"],
                 negative_signals: ["MULTIPLE_CANDIDATES"] }],
};

test("release rows keep candidate evidence and the reason", () => {
  const m = toMention(row);
  assert.equal(m.reason, "2 viable candidates");
  assert.deepEqual(m.candidates[0], { targetId: "per_a", match: "NAME_EXACT", signals: ["NAME_EXACT"],
                                      negativeSignals: ["MULTIPLE_CANDIDATES"], rejected: false });
  assert.equal(RESOLVED_MENTION.has(m.status), false);
  assert.equal(m.kind, "person");
});

test("project mentions resolve to a Project and keep the stated title", () => {
  const m = toMention({
    canonical_id: "pjm_1", stated_title: "OTKA K 143593 - Gyermekvédelem az iskolában – Kutatásvezető",
    source_url: "https://politikatudomany.tk.elte.hu/kutato/kopasz-marianna", observed_on_profile_of: "per_k",
    activity_cues: [], resolution: { status: "HIGH_CONFIDENCE_AUTO", project_id: "prj_g", method: "title_and_owner" },
    candidates: [{ project_id: "prj_g", title_match: "TITLE_EQUAL_AFTER_AFFIXES", signals: ["PAGE_LINKS_OWNER"] }],
  });
  assert.equal(m.kind, "project");
  assert.equal(m.resolvedTo, "prj_g");
  assert.equal(m.observedOnProfileOf, "per_k");
  assert.equal(m.candidates[0].match, "TITLE_EQUAL_AFTER_AFFIXES");
  assert.equal(RESOLVED_MENTION.has(m.status), true);
});

test("Neo4j rows carry the same data as JSON properties", () => {
  const { resolution, candidates, ...rest } = row;
  const m = toMention({ ...rest, resolution_json: JSON.stringify(resolution), candidates_json: JSON.stringify(candidates) });
  assert.deepEqual(m, toMention(row));
});
