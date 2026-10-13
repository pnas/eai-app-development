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

test("Gemini context caching threshold audit matches Enterprise specifications", () => {
  // Gemini 2 family requires >= 2,048 tokens
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(1500, "gemini-2.5-flash"), false);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(2048, "gemini-2.5-flash"), true);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(2500, "gemini-2.5-pro"), true);

  // Gemini 3 family requires >= 4,096 tokens
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(2048, "gemini-3-flash"), false);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(4096, "gemini-3-flash"), true);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(5000, "gemini-3.1-pro"), true);

  // Gemini 3 implicit preview models (e.g. 3.7 Flash, 3.8 Flash) require >= 6,144 tokens
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(5000, "gemini-3.7-flash"), false);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(6144, "gemini-3.7-flash"), true);
  assert.equal(OptimizedPromptBuilder.isGeminiCacheEligible(7000, "gemini-3.8-flash"), true);
});

test("Anthropic caching threshold audit enforces Sonnet/Opus 1024 and Haiku 2048", () => {
  // Claude 5.5, 3.7 & 3.5 Sonnet / Opus
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1000, "claude-sonnet-5-5"), false);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-sonnet-5-5"), true);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-opus-5-5"), true);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1000, "claude-3-7-sonnet-20250219"), false);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-3-7-sonnet-20250219"), true);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-3-5-sonnet-20241022"), true);

  // Claude Haiku
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-haiku-5-5"), false);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(2048, "claude-haiku-5-5"), true);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(1024, "claude-3-5-haiku-20241022"), false);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(2000, "claude-3-haiku-20240307"), false);
  assert.equal(OptimizedPromptBuilder.isAnthropicCacheEligible(2048, "claude-3-5-haiku-20241022"), true);
});

test("OpenAI caching threshold audit enforces 1024 token minimum", () => {
  assert.equal(OptimizedPromptBuilder.isOpenAICacheEligible(1000, "gpt-4o"), false);
  assert.equal(OptimizedPromptBuilder.isOpenAICacheEligible(1023, "gpt-4o-mini"), false);
  assert.equal(OptimizedPromptBuilder.isOpenAICacheEligible(1024, "gpt-4o"), true);
  assert.equal(OptimizedPromptBuilder.isOpenAICacheEligible(2048, "o1"), true);
  assert.equal(OptimizedPromptBuilder.isOpenAICacheEligible(1024, "o3-mini"), true);
});

test("Anthropic breakpoint audit counts breakpoints across system, tools, and messages", () => {
  const payload = {
    model: "claude-3-7-sonnet-20250219",
    system: [
      { type: "text", text: "Policy 1", cache_control: { type: "ephemeral" } },
      { type: "text", text: "Policy 2" },
    ],
    tools: [
      { name: "t1", description: "d1", cache_control: { type: "ephemeral" } },
      { name: "t2", description: "d2" },
    ],
    messages: [
      { role: "user", content: [{ type: "text", text: "q1", cache_control: { type: "ephemeral" } }] },
      { role: "assistant", content: "a1" },
      { role: "user", content: "q2" },
    ],
  };

  const count = OptimizedPromptBuilder.countAnthropicBreakpoints(payload);
  assert.equal(count, 3);
  assert.ok(count <= OptimizedPromptBuilder.MAX_ANTHROPIC_BREAKPOINTS);
});

test("diagnoseCacheMiss reproduces OpenAI diagnostics reasons taxonomy", () => {
  const base = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Ticket");
  base.prompt_cache_key = "tenant-telekom-prod";
  base.reasoning_effort = "medium";

  // 1. Exact match -> cache_hit
  const hitPayload = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Another Ticket");
  hitPayload.prompt_cache_key = "tenant-telekom-prod";
  hitPayload.reasoning_effort = "medium";
  const diagHit = OptimizedPromptBuilder.diagnoseCacheMiss(base, hitPayload);
  assert.equal(diagHit.type, "cache_hit");
  assert.equal(diagHit.reason, null);

  // 2. Model changed
  const mPayload = { ...hitPayload, model: "claude-3-5-sonnet-20241022" };
  const diagModel = OptimizedPromptBuilder.diagnoseCacheMiss(base, mPayload);
  assert.equal(diagModel.type, "cache_miss");
  assert.equal(diagModel.reason, "model_changed");

  // 3. Prompt cache key changed
  const kPayload = { ...hitPayload, prompt_cache_key: "tenant-telekom-staging" };
  const diagKey = OptimizedPromptBuilder.diagnoseCacheMiss(base, kPayload);
  assert.equal(diagKey.type, "cache_miss");
  assert.equal(diagKey.reason, "prompt_cache_key_changed");

  // 4. Reasoning effort changed
  const rPayload = { ...hitPayload, reasoning_effort: "high" };
  const diagReasoning = OptimizedPromptBuilder.diagnoseCacheMiss(base, rPayload);
  assert.equal(diagReasoning.type, "cache_miss");
  assert.equal(diagReasoning.reason, "reasoning_effort_changed");

  // 5. Tools changed
  const tPayload = { ...hitPayload, tools: [{ name: "different_tool", description: "desc" }] };
  const diagTools = OptimizedPromptBuilder.diagnoseCacheMiss(base, tPayload);
  assert.equal(diagTools.type, "cache_miss");
  assert.equal(diagTools.reason, "tools_changed");

  // 6. Input prefix changed
  const iPayload = { ...hitPayload, system: [{ type: "text", text: "Mutated prefix text" }] };
  const diagInput = OptimizedPromptBuilder.diagnoseCacheMiss(base, iPayload);
  assert.equal(diagInput.type, "cache_miss");
  assert.equal(diagInput.reason, "input_changed");
});

test("diagnoseCacheMiss reproduces Anthropic diagnostics reasons taxonomy", () => {
  const base = OptimizedPromptBuilder.buildOptimizedPayload(sampleKb, sampleTools1, "Ticket");
  base.id = "msg_0123456789abcdef";
  base.messages = [
    { role: "user", content: "What is the policy?" },
    { role: "assistant", content: "The policy requires 15m response." },
  ];

  // 1. Exact match / subsequent turn -> cache_hit
  const hitPayload = {
    ...base,
    previous_message_id: "msg_0123456789abcdef",
    messages: [...base.messages, { role: "user", content: "Follow-up question" }],
  };
  const diagHit = OptimizedPromptBuilder.diagnoseCacheMiss(base, hitPayload, "anthropic");
  assert.equal(diagHit.type, "cache_hit");
  assert.equal(diagHit.reason, null);

  // 2. system_changed
  const sysPayload = {
    ...hitPayload,
    system: [{ type: "text", text: "Mutated system instructions", cache_control: { type: "ephemeral" } }],
  };
  const diagSys = OptimizedPromptBuilder.diagnoseCacheMiss(base, sysPayload, "anthropic");
  assert.equal(diagSys.type, "cache_miss");
  assert.equal(diagSys.reason, "system_changed");
  assert.ok((diagSys.cache_missed_input_tokens ?? 0) > 0);

  // 3. messages_changed (prior history altered)
  const msgPayload = {
    ...hitPayload,
    messages: [{ role: "user", content: "Rewritten history" }],
  };
  const diagMsg = OptimizedPromptBuilder.diagnoseCacheMiss(base, msgPayload, "anthropic");
  assert.equal(diagMsg.type, "cache_miss");
  assert.equal(diagMsg.reason, "messages_changed");
  assert.ok((diagMsg.cache_missed_input_tokens ?? 0) > 0);

  // 4. tools_changed
  const toolsPayload = {
    ...hitPayload,
    tools: [{ name: "new_tool", description: "New schema" }],
  };
  const diagTools = OptimizedPromptBuilder.diagnoseCacheMiss(base, toolsPayload, "anthropic");
  assert.equal(diagTools.type, "cache_miss");
  assert.equal(diagTools.reason, "tools_changed");
  assert.ok((diagTools.cache_missed_input_tokens ?? 0) > 0);

  // 5. previous_message_not_found
  const missingPayload = {
    ...hitPayload,
    previous_message_id: "msg_expired_or_invalid",
  };
  const diagMissing = OptimizedPromptBuilder.diagnoseCacheMiss(base, missingPayload, "anthropic");
  assert.equal(diagMissing.type, "cache_miss");
  assert.equal(diagMissing.reason, "previous_message_not_found");
});

test("Anthropic extended 1h TTL and top-level automatic cache breakpoint audit", () => {
  // 1. Extended 1h TTL on system block
  const payload1h = OptimizedPromptBuilder.buildOptimizedPayload(
    sampleKb,
    sampleTools1,
    "Ticket",
    undefined,
    "1h"
  );
  assert.deepEqual(payload1h.system[0].cache_control, { type: "ephemeral", ttl: "1h" });

  // 2. Top-level automatic caching consumes 1 breakpoint slot
  const topLevelPayload = {
    model: "claude-3-7-sonnet-20250219",
    cache_control: { type: "ephemeral" }, // <-- Top-level automatic caching
    system: [
      { type: "text", text: "Policy 1", cache_control: { type: "ephemeral" } },
    ],
    messages: [
      { role: "user", content: "Hello" },
    ],
  };
  const count = OptimizedPromptBuilder.countAnthropicBreakpoints(topLevelPayload);
  assert.equal(count, 2, `Expected 2 breakpoints (1 top-level + 1 system), got ${count}`);
});


