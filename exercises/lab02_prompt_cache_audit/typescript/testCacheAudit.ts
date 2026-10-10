import test from "node:test";
import assert from "node:assert/strict";
import { BrokenPromptBuilder, ToolConfig } from "./starter.js";
import { OptimizedPromptBuilder, computePrefixHash } from "./solution.js";

const sampleKb = "Standard Telecom SLA requires responding to P1 incidents within 15 minutes.";

const sampleTools1: ToolConfig = {
  b_tool: { desc: "Restart modem" },
  a_tool: { desc: "Check balance" },
};

const sampleTools2: ToolConfig = {
  a_tool: { desc: "Check balance" },
  b_tool: { desc: "Restart modem" },
};

test("BrokenPromptBuilder produces cache misses across requests", async () => {
  const p1 = BrokenPromptBuilder.buildPayload(sampleKb, sampleTools1, "Ticket 1");
  await new Promise((r) => setTimeout(r, 10)); // Ensure clock advances
  const p2 = BrokenPromptBuilder.buildPayload(sampleKb, sampleTools1, "Ticket 2");

  const h1 = computePrefixHash(p1.system);
  const h2 = computePrefixHash(p2.system);

  assert.notEqual(h1, h2, "Broken builder was expected to produce different hashes");
});

test("OptimizedPromptBuilder preserves exact prefix hash across tickets and timestamps", () => {
  const p1 = OptimizedPromptBuilder.buildOptimizedPayload(
    sampleKb,
    sampleTools1,
    "Customer cannot connect to 5G",
    "2026-10-10T10:00:00Z"
  );
  const p2 = OptimizedPromptBuilder.buildOptimizedPayload(
    sampleKb,
    sampleTools1,
    "Billing query for invoice #999",
    "2026-10-10T10:05:00Z"
  );

  const h1 = computePrefixHash(p1.system);
  const h2 = computePrefixHash(p2.system);

  assert.equal(h1, h2, "Prefix hashes must be 100% identical for cache hits!");
});

test("Deterministic tool serialization handles insertion order variations", () => {
  const p1 = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Test");
  const p2 = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools2, "Test");

  const h1 = computePrefixHash(p1.system);
  const h2 = computePrefixHash(p2.system);

  assert.equal(h1, h2, "Tool object key order must not invalidate cache hash");
});

test("Static block meets minimum 1024 token threshold", () => {
  const p = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Test");
  const systemText = p.system[0].text;
  const tokens = OptimizedPromptBuilder.estimateTokens(systemText);

  assert.ok(tokens >= 1024, `Estimated tokens ${tokens} must be >= 1024`);
});

test("Cache control is placed on system prefix and absent from user message", () => {
  const p = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Test");

  assert.deepEqual(p.system[0].cache_control, { type: "ephemeral" });
  assert.equal(typeof p.messages[0].content, "string");
});

