/**
 * Unit Test Suite for TypeScript LangChain Model Factory & Frontier Models.
 */

import assert from "node:assert/strict";
import pc from "picocolors";
import {
  DEFAULT_MODELS,
  PRIMARY_MODELS,
  isReasoningModel,
  isSamplingRestrictedAnthropic,
  getChatModel,
  getResilientCascade,
} from "./src/langchain_suite/core/models.js";

async function runTests() {
  console.log(pc.bold(pc.cyan("\n=== Testing TypeScript LangChain Model Factory & Frontier Mappings ===\n")));

  // Mock API keys for factory instantiation tests
  process.env.OPENAI_API_KEY = process.env.OPENAI_API_KEY || "sk-mock-key-12345";
  process.env.ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || "sk-ant-mock-key-12345";
  process.env.GEMINI_API_KEY = process.env.GEMINI_API_KEY || "mock-gemini-key-12345";

  let passed = 0;
  let total = 0;

  function test(name: string, fn: () => void) {
    total++;
    try {
      fn();
      console.log(pc.green(`  ✔ ${name}`));
      passed++;
    } catch (err: any) {
      console.error(pc.red(`  ✖ ${name}: ${err.message}`));
      throw err;
    }
  }

  // 1. Verify default frontier models
  test("DEFAULT_MODELS configured to latest generation frontier models", () => {
    assert.equal(DEFAULT_MODELS.openai, "gpt-4.1-mini");
    assert.equal(DEFAULT_MODELS.anthropic, "claude-haiku-5-5");
    assert.equal(DEFAULT_MODELS.gemini, "gemini-3.8-flash");
  });

  // 2. Verify PRIMARY_MODELS catalog
  test("PRIMARY_MODELS catalog contains reasoning, high-throughput, and legacy tiers", () => {
    assert.ok(PRIMARY_MODELS.openai.flagship_reasoning.includes("gpt-6-astra"));
    assert.ok(PRIMARY_MODELS.openai.high_throughput.includes("gpt-4.1-mini"));
    assert.ok(PRIMARY_MODELS.openai.legacy.includes("gpt-4o-mini"));
    assert.ok(PRIMARY_MODELS.anthropic.flagship.includes("claude-haiku-5-5"));
    assert.ok(PRIMARY_MODELS.anthropic.v4_5_class.includes("claude-sonnet-4-5"));
    assert.ok(PRIMARY_MODELS.anthropic.legacy.includes("claude-3-5-sonnet"));
    assert.ok(PRIMARY_MODELS.gemini.flagship.includes("gemini-3.8-flash"));
    assert.ok(PRIMARY_MODELS.gemini.frontier.includes("gemini-3.1-pro-preview"));
  });

  // 3. Reasoning model detection (gpt-6*, o1*, o3*, o4*)
  test("isReasoningModel accurately identifies reasoning models vs standard models", () => {
    assert.equal(isReasoningModel("gpt-6-astra"), true);
    assert.equal(isReasoningModel("gpt-6.1-sol"), true);
    assert.equal(isReasoningModel("gpt-6-luna"), true);
    assert.equal(isReasoningModel("o1-preview"), true);
    assert.equal(isReasoningModel("o3-mini"), true);
    assert.equal(isReasoningModel("o4-mini"), true);

    assert.equal(isReasoningModel("gpt-4.1-mini"), false);
    assert.equal(isReasoningModel("gpt-4.1"), false);
    assert.equal(isReasoningModel("gpt-4o"), false);
    assert.equal(isReasoningModel("gpt-4o-mini"), false);
    assert.equal(isReasoningModel("gpt-4-turbo"), false);
  });

  // 4. Anthropic sampling constraint detection (Claude 4.7+, 5.x vs Claude 4.5, 3.x)
  test("isSamplingRestrictedAnthropic accurately identifies Claude 4.7+/5.x vs 4.5/3.x", () => {
    assert.equal(isSamplingRestrictedAnthropic("claude-opus-5-5"), true);
    assert.equal(isSamplingRestrictedAnthropic("claude-sonnet-5-5"), true);
    assert.equal(isSamplingRestrictedAnthropic("claude-haiku-5-5"), true);
    assert.equal(isSamplingRestrictedAnthropic("claude-fable-5-1"), true);
    assert.equal(isSamplingRestrictedAnthropic("claude-mythos-5-1"), true);
    assert.equal(isSamplingRestrictedAnthropic("claude-opus-4.7"), true);

    assert.equal(isSamplingRestrictedAnthropic("claude-opus-4-5"), false);
    assert.equal(isSamplingRestrictedAnthropic("claude-sonnet-4-5"), false);
    assert.equal(isSamplingRestrictedAnthropic("claude-haiku-4-5"), false);
    assert.equal(isSamplingRestrictedAnthropic("claude-3-5-sonnet-20241022"), false);
    assert.equal(isSamplingRestrictedAnthropic("claude-3-opus-20240229"), false);
  });

  // 5. OpenAI instantiation (temperature preserved on standard, stripped on reasoning)
  test("OpenAI model instantiation handles temperature properly for standard vs reasoning", () => {
    const std = getChatModel("openai", { model: "gpt-4.1-mini", temperature: 0.2 }) as any;
    assert.equal(std.modelName || std.model, "gpt-4.1-mini");
    assert.equal(std.temperature, 0.2);

    const legacy = getChatModel("openai", { model: "gpt-4-turbo", temperature: 0.7 }) as any;
    assert.equal(legacy.modelName || legacy.model, "gpt-4-turbo");
    assert.equal(legacy.temperature, 0.7);

    const reasoning = getChatModel("openai", { model: "gpt-6-astra", temperature: 0.7 }) as any;
    assert.equal(reasoning.modelName || reasoning.model, "gpt-6-astra");
    assert.equal(reasoning.temperature, undefined);
  });

  // 6. Anthropic instantiation (temperature preserved on 4.5, stripped on 5.5)
  test("Anthropic model instantiation handles temperature properly for 4.5 vs 5.5", () => {
    const m45 = getChatModel("anthropic", { model: "claude-sonnet-4-5", temperature: 0.3 }) as any;
    assert.equal(m45.modelName || m45.model, "claude-sonnet-4-5");
    assert.equal(m45.temperature, 0.3);

    const m55 = getChatModel("anthropic", { model: "claude-haiku-5-5", temperature: 0.5 }) as any;
    assert.equal(m55.modelName || m55.model, "claude-haiku-5-5");
    assert.equal(m55.temperature, undefined);
  });

  // 7. Gemini instantiation (latest 3.8 and preview 3.1)
  test("Gemini model instantiation handles 3.8-flash and 3.1-pro-preview", () => {
    const latest = getChatModel("gemini", { model: "gemini-3.8-flash", temperature: 0.4 }) as any;
    assert.equal(latest.modelName || latest.model, "gemini-3.8-flash");
    assert.equal(latest.temperature, 0.4);

    const preview = getChatModel("gemini", { model: "gemini-3.1-pro-preview", temperature: 0.1 }) as any;
    assert.equal(preview.modelName || preview.model, "gemini-3.1-pro-preview");
    assert.equal(preview.temperature, 0.1);
  });

  // 8. Resilient cascade instantiation
  test("getResilientCascade constructs 3-tier fallback chain across providers", () => {
    const cascade = getResilientCascade({
      primaryModel: "claude-haiku-5-5",
      secondaryModel: "gpt-4.1-mini",
      tertiaryModel: "gemini-3.8-flash",
    });
    assert.ok(cascade !== null && cascade !== undefined);
  });

  console.log(pc.bold(pc.green(`\n✔ All ${passed}/${total} model factory tests passed!\n`)));
}

runTests().catch((err) => {
  console.error(err);
  process.exit(1);
});
