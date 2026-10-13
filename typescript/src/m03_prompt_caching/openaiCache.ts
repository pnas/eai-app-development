/**
 * Module 3: OpenAI Prompt Caching, Diagnostics & Monitoring (TypeScript).
 *
 * Demonstrates OpenAI's prompt caching architecture across model generations:
 * 1. Classic Implicit Prefix Caching (GPT-4o, GPT-4o-mini, o1, o3-mini):
 *    - Automatic prefix matching for prompts >= 1,024 tokens.
 *    - 128-token increment block granularity.
 *    - 50% discount on cache reads (0.50x); 0% write surcharge (1.00x).
 *    - Cache retention options: "in_memory" (5-10m) vs "24h".
 *    - Routing with prompt_cache_key (~15 req/min target per key).
 *
 * 2. Modern GPT-5.6+ / GPT-6 Dual-Mode Caching (Responses API):
 *    - Explicit mode: prompt_cache_options: { mode: "explicit" }.
 *    - Explicit breakpoints: prompt_cache_breakpoint: true.
 *    - Economics: 1.25x write surcharge, 0.10x read discount (90% off; 95% off on GPT-6.1 Sol: 0.05x).
 *    - Prewarming: prompt_cache_options.prewarm: true for zero-latency TTFT.
 *    - Cache TTL: prompt_cache_options.ttl: "30m" (minimum 30 min rolling).
 *    - Multi-tenant isolation: prompt_cache_key for tenant accounting & anti-probing.
 *
 * 3. Prompt Cache Diagnostics & Monitoring:
 *    - prompt_cache_options.comparison_response_id: compares against baseline response.
 *    - prompt_cache_diagnostics: type ("cache_hit", "cache_miss"), reason ("tools_changed",
 *      "input_changed", "reasoning_effort_changed", etc.), and cache_missed_tokens.
 *    - Weighted input token cost calculation.
 *
 * Official References:
 * - Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
 * - Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
 */

import pc from "picocolors";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";

// Synthetic enterprise knowledge base >= 1,024 tokens
const LARGE_RUNBOOK = `
# TELEKOM INFRASTRUCTURE RUNBOOK: HYPER-CONVERGED KUBERNETES DEPLOYMENTS
[Chapter 1: Network Ingress Topology]
The ingress architecture utilizes Envoy proxy instances configured with circuit breaking,
rate limiting, and mTLS verification using SPIFFE/SPIRE identity documents.
Each ingress pod handles up to 10,000 active concurrent WebSocket connections.
[Chapter 2: Storage Classes and CSI Drivers]
Persistent volumes are provisioned via Ceph CSI with triple replication across failure domains.
Snapshots must be scheduled every 4 hours with 30-day immutable retention policies.
[Chapter 3: Node Autoscaling & Eviction Policies]
Karpenter manages EC2 node lifecycle. Pod Disruption Budgets (PDB) must guarantee minAvailable: 80%
at all times during spot node termination events.
[Chapter 4: Service Mesh & Observability]
Istio ambient mesh operates without sidecars using ztunnel for mTLS and waypoint proxies for L7 policies.
Telemetry spans are sampled at 10% for nominal traffic and 100% for error traces.
`.concat("\nAll cluster metrics are ingested into Prometheus and persisted to long-term Thanos storage.\n".repeat(50));

export function calculateInputCost(
  inputTokens: number,
  cachedTokens: number,
  cacheWriteTokens: number = 0,
  pricePerMillion: number = 0.15,
  cacheReadMultiplier: number = 0.50,
  cacheWriteMultiplier: number = 1.00
): number {
  /**
   * Calculate weighted input token cost following official OpenAI monitoring formulas.
   *
   * For GPT-4o / GPT-4o-mini:
   *   - Read multiplier = 0.50 (50% off)
   *   - Write multiplier = 1.00 (standard price)
   * For GPT-5.6+ / GPT-6 (e.g. gpt-6-astra, gpt-6.1-sol):
   *   - Read multiplier = 0.10 (90% off) or 0.05 (95% off on gpt-6.1-sol)
   *   - Write multiplier = 1.25 (25% surcharge)
   */
  const ordinaryInputTokens = inputTokens - cachedTokens - cacheWriteTokens;
  const weightedInputTokens =
    ordinaryInputTokens +
    cachedTokens * cacheReadMultiplier +
    cacheWriteTokens * cacheWriteMultiplier;
  return (weightedInputTokens * pricePerMillion) / 1_000_000;
}

export function demoOpenAIExplicitCaching(): void {
  console.log(pc.bold(pc.green("\n=== Responses API Explicit Caching Breakdown (GPT-6.1 Sol / GPT-6 Astra) ===")));
  console.log(
    `• ${pc.bold("Explicit Breakpoints")}: Developer controls exact cache boundary via prompt_cache_breakpoint.\n` +
    `• ${pc.bold("Pricing Economics")}:\n` +
    `  - Initial Write: 1.25x surcharge on prompt write.\n` +
    `  - Subsequent Reads: 0.10x (90% off) on standard GPT-6, 0.05x (95% off) on GPT-6.1 Sol!\n` +
    `• ${pc.bold("Prewarming")}: prompt_cache_options: { prewarm: true } eliminates TTFT penalty on first user query.\n`
  );

  const basePrice = 2.50; // per 1M tokens
  const promptTokens = 10000;
  const uncached10 = 10 * ((promptTokens * basePrice) / 1_000_000);

  const classic10 = ((promptTokens * 1.0 * basePrice) / 1_000_000) + 9 * ((promptTokens * 0.50 * basePrice) / 1_000_000);
  const gpt6_10 = ((promptTokens * 1.25 * basePrice) / 1_000_000) + 9 * ((promptTokens * 0.10 * basePrice) / 1_000_000);
  const sol10 = ((promptTokens * 1.25 * basePrice) / 1_000_000) + 9 * ((promptTokens * 0.05 * basePrice) / 1_000_000);

  console.table({
    "Uncached (Baseline)": {
      "Initial Write ($)": `$${(uncached10 / 10).toFixed(5)}`,
      "Subsequent Hit ($)": `$${(uncached10 / 10).toFixed(5)}`,
      "10-Turn Total ($)": `$${uncached10.toFixed(5)}`,
      "Net Savings": "0% (Baseline)",
    },
    "Classic Implicit (50% read)": {
      "Initial Write ($)": `$${((promptTokens * 1.0 * basePrice) / 1_000_000).toFixed(5)}`,
      "Subsequent Hit ($)": `$${((promptTokens * 0.50 * basePrice) / 1_000_000).toFixed(5)}`,
      "10-Turn Total ($)": `$${classic10.toFixed(5)}`,
      "Net Savings": `${(((uncached10 - classic10) / uncached10) * 100).toFixed(1)}%`,
    },
    "Modern GPT-6 Explicit (90% read)": {
      "Initial Write ($)": `$${((promptTokens * 1.25 * basePrice) / 1_000_000).toFixed(5)}`,
      "Subsequent Hit ($)": `$${((promptTokens * 0.10 * basePrice) / 1_000_000).toFixed(5)}`,
      "10-Turn Total ($)": `$${gpt6_10.toFixed(5)}`,
      "Net Savings": `${(((uncached10 - gpt6_10) / uncached10) * 100).toFixed(1)}%`,
    },
    "GPT-6.1 Sol Explicit (95% read)": {
      "Initial Write ($)": `$${((promptTokens * 1.25 * basePrice) / 1_000_000).toFixed(5)}`,
      "Subsequent Hit ($)": `$${((promptTokens * 0.05 * basePrice) / 1_000_000).toFixed(5)}`,
      "10-Turn Total ($)": `$${sol10.toFixed(5)}`,
      "Net Savings": `${(((uncached10 - sol10) / uncached10) * 100).toFixed(1)}%`,
    },
  });
}

export function explainPromptCacheDiagnostics(): void {
  console.log(pc.bold(pc.cyan("\n=== OpenAI Prompt Cache Diagnostics Taxonomy (comparison_response_id) ===")));
  const taxonomies = [
    {
      type: "cache_miss",
      reason: "tools_changed",
      cause: "Tools added, removed, reordered, or schema mutated",
      fix: "Keep tool list deterministically sorted; use tool_choice='none' or allowed_tools",
    },
    {
      type: "cache_miss",
      reason: "model_changed",
      cause: "Routing, fallback, or A/B test selected another model",
      fix: "Pin model name; ensure cache-sharing requests route to identical model version",
    },
    {
      type: "cache_miss",
      reason: "prompt_cache_key_changed",
      cause: "Key changed between requests",
      fix: "Keep stable prompt_cache_key per tenant/workflow; avoid random UUIDs",
    },
    {
      type: "cache_miss",
      reason: "input_changed",
      cause: "Timestamp, user ID, or dynamic token injected in prefix",
      fix: "Move volatile data after prefix or into user message; keep prefix byte-identical",
    },
    {
      type: "cache_miss",
      reason: "reasoning_effort_changed",
      cause: "Top-level reasoning.effort modified",
      fix: "Use configuration_update input item mid-conversation on GPT-6 models",
    },
    {
      type: "cache_miss",
      reason: "text_format_changed",
      cause: "Output format / Structured Output schema changed",
      fix: "Keep text.format and JSON schema identical across requests",
    },
    {
      type: "cache_miss",
      reason: "context_compacted",
      cause: "Compaction replaced earlier conversation history",
      fix: "Preserve stable instructions before compacted summary",
    },
    {
      type: "cache_miss",
      reason: "service_tier_changed",
      cause: "Scale-tier or default routing tier switched",
      fix: "Ensure service_tier is consistent across pipeline",
    },
    {
      type: "cache_hit",
      reason: "N/A",
      cause: "Expected prefix successfully matched and reused",
      fix: "Inspect usage.prompt_tokens_details.cached_tokens for actual token count",
    },
  ];

  for (const item of taxonomies) {
    const typeLabel = item.type === "cache_hit" ? pc.green(`[${item.type}]`) : pc.yellow(`[${item.type}]`);
    console.log(
      `${typeLabel} ${pc.bold(item.reason.padEnd(26))} | ${pc.white(item.cause)}\n` +
      `  └─ ${pc.dim("Remediation:")} ${pc.cyan(item.fix)}`
    );
  }
}

async function runOpenAICachingDemo() {
  console.log(pc.bold(pc.cyan("\n=== OpenAI Prompt Caching & Diagnostics Architecture (TypeScript) ===")));
  console.log(
    `• ${pc.bold("Classic Models (GPT-4o, GPT-4o-mini, o1)")}:\n` +
    `  - Automatic prefix matching >= 1,024 tokens in ${pc.yellow("128-token increments")}.\n` +
    `  - 50% read discount (0.50x), 0% write surcharge.\n` +
    `  - Retention: ${pc.green("'in_memory'")} (5-10m) or ${pc.green("'24h'")} extended retention.\n` +
    `  - Routing: ${pc.yellow("prompt_cache_key")} routes related traffic (~15 req/min per key).\n\n` +
    `• ${pc.bold("Modern Models (GPT-5.6+, GPT-6, GPT-6.1 Sol)")}:\n` +
    `  - Dual-mode: ${pc.green("explicit")} (prompt_cache_breakpoint) vs ${pc.green("implicit")}.\n` +
    `  - Economics: 1.25x write surcharge, 0.10x read (90% discount; 95% on GPT-6.1 Sol).\n` +
    `  - Prewarming: ${pc.yellow("prompt_cache_options.prewarm: true")} for zero-latency TTFT.\n` +
    `  - Diagnostics: ${pc.magenta("prompt_cache_options.comparison_response_id")} explains misses.\n`
  );

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.startsWith("mock") || apiKey.startsWith("sk-placeholder")) {
    console.log(pc.yellow("[Simulated Offline Demonstration] Displaying prefix caching metrics..."));
    console.table([
      { Call: "Call #1", Query: "What is the required minAvailable...", TotalPromptTok: 1420, CachedTok: 0, UncachedTok: 1420, Cost: "$0.000213", Latency: "1.24s" },
      { Call: "Call #2", Query: "What CSI driver is used for persi...", TotalPromptTok: 1428, CachedTok: 1420, UncachedTok: 8, Cost: "$0.000108", Latency: "0.31s" },
      { Call: "Call #3", Query: "What is the sampling rate for nom...", TotalPromptTok: 1435, CachedTok: 1420, UncachedTok: 15, Cost: "$0.000109", Latency: "0.29s" },
    ]);
    demoOpenAIExplicitCaching();
    explainPromptCacheDiagnostics();
    return;
  }

  const client = getOpenAIClient();
  const model = "gpt-4o-mini";

  const queries = [
    "What is the required minAvailable percentage in Pod Disruption Budgets?",
    "What CSI driver is used for persistent volumes and how often are snapshots taken?",
    "What is the sampling rate for nominal vs error traces in the Istio ambient mesh?",
  ];

  for (let idx = 0; idx < queries.length; idx++) {
    const query = queries[idx];
    const messages: any[] = [
      { role: "system", content: `You are a Telekom SRE runbook assistant.\n\n${LARGE_RUNBOOK}` },
      { role: "user", content: query },
    ];

    const start = performance.now();
    const response = await client.chat.completions.create({
      model,
      messages,
      max_tokens: 150,
      temperature: 0.0,
    });
    const elapsed = ((performance.now() - start) / 1000).toFixed(2);

    const usage: any = response.usage;
    const promptTokens = usage?.prompt_tokens ?? 0;
    const cachedTokens = usage?.prompt_tokens_details?.cached_tokens ?? 0;
    const uncachedTokens = promptTokens - cachedTokens;
    const cost = calculateInputCost(promptTokens, cachedTokens, 0, 0.15, 0.50, 1.00);

    console.log(
      pc.cyan(`Call #${idx + 1}: `) +
      pc.white(`"${query.slice(0, 32)}..." | `) +
      pc.gray(`Total: ${promptTokens} | `) +
      pc.green(`Cached (Hit): ${cachedTokens} | `) +
      pc.yellow(`Uncached: ${uncachedTokens} | `) +
      pc.bold(pc.green(`Cost: $${cost.toFixed(6)} | `)) +
      pc.magenta(`Latency: ${elapsed}s`)
    );
  }

  demoOpenAIExplicitCaching();
  explainPromptCacheDiagnostics();
}

if (process.argv[1]?.includes("openaiCache")) {
  runOpenAICachingDemo().catch(console.error);
}
