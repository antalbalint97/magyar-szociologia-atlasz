import assert from "node:assert/strict";
import { test } from "node:test";
import { fold, score } from "./search.ts";

test("diacritics are folded", () => {
  assert.equal(fold("Ságvári Bence"), "sagvari bence");
  assert.equal(fold("Erőss Gábor"), "eross gabor");
});

test("query without accents finds accented names", () => {
  assert.ok(score("koltai julia", ["Koltai Júlia"]) > 0.9);
  assert.ok(score("Ferge", ["Ferge Zsuzsa"]) > 0.8);
});

test("prefix and small typos match, unrelated names do not", () => {
  assert.ok(score("kisfal", ["Kisfalusi Dorottya"]) > 0.5);
  assert.ok(score("feishmidt", ["Feischmidt Margit"]) > 0.3);
  assert.equal(score("koltai", ["Kmetty Zoltán"]), 0);
});

test("multi-word topic queries", () => {
  assert.ok(score("network analysis", ["Network analysis", "Hálózatelemzés"]) > 0.9);
  assert.ok(score("halozat", ["Hálózatelemzés"]) > 0.5);
  assert.equal(score("roma mobility", ["Roma studies"]), 0);
});
