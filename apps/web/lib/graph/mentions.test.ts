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
  assert.deepEqual(m.candidates[0], { personId: "per_a", nameMatch: "NAME_EXACT", signals: ["NAME_EXACT"],
                                      negativeSignals: ["MULTIPLE_CANDIDATES"], rejected: false });
  assert.equal(RESOLVED_MENTION.has(m.status), false);
});

test("Neo4j rows carry the same data as JSON properties", () => {
  const { resolution, candidates, ...rest } = row;
  const m = toMention({ ...rest, resolution_json: JSON.stringify(resolution), candidates_json: JSON.stringify(candidates) });
  assert.deepEqual(m, toMention(row));
});
