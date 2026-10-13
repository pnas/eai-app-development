/**
 * Module 6: Enterprise GenAI Cost & ROI Calculator (TypeScript).
 *
 * Calculates exact financial economics across production optimization strategies:
 * 1. Baseline Realtime Uncached
 * 2. Upstream Prompt Caching (50% to 95% read discount)
 * 3. Synchronous Flex Processing (50% flat discount) & Asynchronous Batch API
 * 4. Fast Mode Latency Optimization (1.5x - 2.0x premium for 2.5x speedup)
 * 5. Tiered Routing (80% traffic offloaded to fast/cheap model)
 * 6. Enterprise Gateway Tier: Tiered Routing + Prompt Caching + Gateway Semantic Caching
 *
 * Official References:
 * - Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
 * - Fast Mode: https://developers.openai.com/api/docs/guides/fast-mode
 * - Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
 * - Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
 * - Batch API: https://developers.openai.com/api/docs/guides/batch
 */

import pc from "picocolors";

export interface PricingModel {
  name: string;
  inputPerM: number;
  outputPerM: number;
  cacheReadPerM: number;
  batchDiscountMultiplier?: number;
  fastModeMultiplier?: number;
  flexDiscountMultiplier?: number;
}

export const PRICING: Record<string, PricingModel> = {
  "gpt-6.1-sol": {
    name: "OpenAI GPT-6.1 Sol (Flagship Reasoning)",
    inputPerM: 2.5,
    outputPerM: 10.0,
    cacheReadPerM: 0.125, // 95% discount (0.05x)
    batchDiscountMultiplier: 0.5,
    fastModeMultiplier: 1.75,
    flexDiscountMultiplier: 0.5,
  },
  "gpt-6-astra": {
    name: "OpenAI GPT-6 Astra (Balanced Reasoning)",
    inputPerM: 2.0,
    outputPerM: 8.0,
    cacheReadPerM: 0.20, // 90% discount (0.10x)
    batchDiscountMultiplier: 0.5,
    fastModeMultiplier: 1.75,
    flexDiscountMultiplier: 0.5,
  },
  "gpt-6-luna": {
    name: "OpenAI GPT-6 Luna (Lightweight Reasoning)",
    inputPerM: 0.5,
    outputPerM: 2.0,
    cacheReadPerM: 0.05, // 90% discount (0.10x)
    batchDiscountMultiplier: 0.5,
    fastModeMultiplier: 1.75,
    flexDiscountMultiplier: 0.5,
  },
  "gpt-4.1": {
    name: "OpenAI GPT-4.1 (General Instruction)",
    inputPerM: 2.0,
    outputPerM: 8.0,
    cacheReadPerM: 0.20, // 90% discount (0.10x)
    batchDiscountMultiplier: 0.5,
    fastModeMultiplier: 1.75,
    flexDiscountMultiplier: 0.5,
  },
  "gpt-4.1-mini": {
    name: "OpenAI GPT-4.1 Mini (High Throughput)",
    inputPerM: 0.15,
    outputPerM: 0.60,
    cacheReadPerM: 0.015, // 90% discount (0.10x)
    batchDiscountMultiplier: 0.5,
    fastModeMultiplier: 1.75,
    flexDiscountMultiplier: 0.5,
  },
  "claude-sonnet-5-5": {
    name: "Claude Sonnet 5.5",
    inputPerM: 3.0,
    outputPerM: 15.0,
    cacheReadPerM: 0.15, // 95% discount
    batchDiscountMultiplier: 0.5,
  },
  "claude-haiku-5-5": {
    name: "Claude Haiku 5.5",
    inputPerM: 0.8,
    outputPerM: 4.0,
    cacheReadPerM: 0.08, // 90% discount
    batchDiscountMultiplier: 0.5,
  },
  "claude-3-5-sonnet": {
    name: "Claude 3.5 Sonnet",
    inputPerM: 3.0,
    outputPerM: 15.0,
    cacheReadPerM: 0.3, // 90% discount
    batchDiscountMultiplier: 0.5,
  },
  "claude-3-5-haiku": {
    name: "Claude 3.5 Haiku",
    inputPerM: 0.8,
    outputPerM: 4.0,
    cacheReadPerM: 0.08, // 90% discount
    batchDiscountMultiplier: 0.5,
  },
  "gpt-4o": {
    name: "OpenAI GPT-4o",
    inputPerM: 2.5,
    outputPerM: 10.0,
    cacheReadPerM: 1.25, // 50% discount
    batchDiscountMultiplier: 0.5,
  },
  "gpt-4o-mini": {
    name: "OpenAI GPT-4o-mini",
    inputPerM: 0.15,
    outputPerM: 0.60,
    cacheReadPerM: 0.075, // 50% discount
    batchDiscountMultiplier: 0.5,
  },
  "gemini-2.0-flash": {
    name: "Google Gemini 2.0 Flash",
    inputPerM: 0.10,
    outputPerM: 0.40,
    cacheReadPerM: 0.025, // 75% discount
    batchDiscountMultiplier: 0.5,
  },
};

export const MODEL_CATALOG = PRICING;

export interface MultiModelCostResult {
  promptTokens: number;
  completionTokens: number;
  costs: Array<{
    model: string;
    promptCost: number;
    completionCost: number;
    totalCost: number;
    savingsVsSonnetPercent: number;
  }>;
}

export function calculateMultiModelCosts(
  promptTokens: number,
  completionTokens: number
): MultiModelCostResult {
  const sonnet = PRICING["claude-3-5-sonnet"];
  const baselineCost =
    (promptTokens / 1_000_000) * sonnet.inputPerM +
    (completionTokens / 1_000_000) * sonnet.outputPerM;

  const costs = Object.entries(PRICING).map(([key, pricing]) => {
    const promptCost = (promptTokens / 1_000_000) * pricing.inputPerM;
    const completionCost = (completionTokens / 1_000_000) * pricing.outputPerM;
    const totalCost = promptCost + completionCost;
    const savingsVsSonnetPercent =
      baselineCost > 0 ? ((baselineCost - totalCost) / baselineCost) * 100 : 0;

    return {
      model: key,
      promptCost,
      completionCost,
      totalCost,
      savingsVsSonnetPercent,
    };
  });

  costs.sort((a, b) => a.totalCost - b.totalCost);

  return {
    promptTokens,
    completionTokens,
    costs,
  };
}

export interface RoutingDecision {
  query: string;
  recommendedTier: "FAST-ECONOMY" | "HIGH-REASONING";
  selectedModel: string;
  estimatedCostPerMillion: number;
  reasoning: string;
}

export function recommendTieredRouting(prompt: string): RoutingDecision {
  const complexKeywords = [
    "architecture",
    "distributed",
    "migration",
    "rfc",
    "security audit",
    "root cause",
    "concurrency",
    "reconciliation",
  ];

  const lower = prompt.toLowerCase();
  const isComplex =
    complexKeywords.some((kw) => lower.includes(kw)) ||
    prompt.split(/\s+/).length > 25;

  if (isComplex) {
    return {
      query: prompt.length > 50 ? prompt.slice(0, 47) + "..." : prompt,
      recommendedTier: "HIGH-REASONING",
      selectedModel: "claude-3-5-sonnet",
      estimatedCostPerMillion: 3.0,
      reasoning: "Complex architectural or multi-constraint reasoning query.",
    };
  }

  return {
    query: prompt.length > 50 ? prompt.slice(0, 47) + "..." : prompt,
    recommendedTier: "FAST-ECONOMY",
    selectedModel: "gpt-4o-mini",
    estimatedCostPerMillion: 0.15,
    reasoning: "Standard factual or operational lookup; fast-economy tier adequate.",
  };
}

export interface SemanticCacheROIResult {
  model: string;
  monthlyRequests: number;
  cacheHitRate: number;
  uncachedCostUsd: number;
  cacheCostUsd: number;
  netSavingsUsd: number;
  savingsPercent: number;
}

export function calculateSemanticCacheROI(
  modelKey: string,
  monthlyRequests: number,
  cacheHitRate = 0.35,
  avgInputTokens = 1500,
  avgOutputTokens = 350
): SemanticCacheROIResult {
  const pricing = PRICING[modelKey] ?? PRICING["claude-3-5-haiku"];
  const costPerReq =
    (avgInputTokens / 1_000_000) * pricing.inputPerM +
    (avgOutputTokens / 1_000_000) * pricing.outputPerM;

  const uncachedCostUsd = monthlyRequests * costPerReq;
  const servedByCache = monthlyRequests * cacheHitRate;
  const forwardedToLLM = monthlyRequests - servedByCache;
  const cacheCostUsd = forwardedToLLM * costPerReq;
  const netSavingsUsd = uncachedCostUsd - cacheCostUsd;
  const savingsPercent = uncachedCostUsd > 0 ? (netSavingsUsd / uncachedCostUsd) * 100 : 0;

  return {
    model: pricing.name,
    monthlyRequests,
    cacheHitRate,
    uncachedCostUsd,
    cacheCostUsd,
    netSavingsUsd,
    savingsPercent,
  };
}

export function calculateMonthlySavings(
  primary: PricingModel,
  economy: PricingModel,
  monthlyRequests: number,
  staticPrefixTokens: number,
  dynamicInputTokens: number,
  outputTokens: number,
  semanticCacheHitRate = 0.25,
  economyOffloadRatio = 0.80
) {
  const totalInputPerReq = staticPrefixTokens + dynamicInputTokens;

  // 1. Baseline: Uncached Realtime on Primary Model
  const baseInputCost = (monthlyRequests * totalInputPerReq / 1_000_000) * primary.inputPerM;
  const baseOutputCost = (monthlyRequests * outputTokens / 1_000_000) * primary.outputPerM;
  const baseline = baseInputCost + baseOutputCost;

  // 2. Realtime with Prompt Caching
  const cachedPrefixCost = (monthlyRequests * staticPrefixTokens / 1_000_000) * primary.cacheReadPerM;
  const dynamicInCost = (monthlyRequests * dynamicInputTokens / 1_000_000) * primary.inputPerM;
  const caching = cachedPrefixCost + dynamicInCost + baseOutputCost;

  // 3. Batch API (50% flat discount)
  const batch = baseline * (primary.batchDiscountMultiplier ?? 0.5);

  // 4. Combined: Batch + Prompt Caching
  const combined = caching * (primary.batchDiscountMultiplier ?? 0.5);

  // 5. Tiered Routing (e.g. 80% to economy, 20% to primary)
  const primaryReqs = monthlyRequests * (1.0 - economyOffloadRatio);
  const economyReqs = monthlyRequests * economyOffloadRatio;
  const tieredPrimary = (primaryReqs * totalInputPerReq / 1_000_000) * primary.inputPerM + (primaryReqs * outputTokens / 1_000_000) * primary.outputPerM;
  const tieredEconomy = (economyReqs * totalInputPerReq / 1_000_000) * economy.inputPerM + (economyReqs * outputTokens / 1_000_000) * economy.outputPerM;
  const tiered = tieredPrimary + tieredEconomy;

  // 6. Enterprise Gateway: Semantic Caching (25% hit @ $0) + Tiered Routing + Prompt Caching
  const effectiveReqs = monthlyRequests * (1.0 - semanticCacheHitRate);
  const effPrimaryReqs = effectiveReqs * (1.0 - economyOffloadRatio);
  const effEconomyReqs = effectiveReqs * economyOffloadRatio;

  const gwPrimary = (
    (effPrimaryReqs * staticPrefixTokens / 1_000_000) * primary.cacheReadPerM +
    (effPrimaryReqs * dynamicInputTokens / 1_000_000) * primary.inputPerM +
    (effPrimaryReqs * outputTokens / 1_000_000) * primary.outputPerM
  );
  const gwEconomy = (
    (effEconomyReqs * staticPrefixTokens / 1_000_000) * economy.cacheReadPerM +
    (effEconomyReqs * dynamicInputTokens / 1_000_000) * economy.inputPerM +
    (effEconomyReqs * outputTokens / 1_000_000) * economy.outputPerM
  );
  const gatewayFull = gwPrimary + gwEconomy;

  return { baseline, caching, batch, combined, tiered, gatewayFull };
}

function main() {
  console.log(pc.bold("\n=== Enterprise GenAI Cost Optimization ROI Model (TypeScript) ===\n"));

  const requests = 1_000_000;
  const prefixTok = 4_000;
  const dynamicTok = 500;
  const outputTok = 300;

  const primary = PRICING["claude-3-5-sonnet"];
  const economy = PRICING["gpt-4o-mini"];

  const results = calculateMonthlySavings(primary, economy, requests, prefixTok, dynamicTok, outputTok);

  console.log(pc.cyan(`Primary: ${primary.name} | Economy: ${economy.name} (Volume: ${requests.toLocaleString()} reqs/month)`));
  console.log("--------------------------------------------------------------------------------");
  console.log(`1. Baseline (Uncached Realtime):       $${results.baseline.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo`);

  const cacheSaved = results.baseline - results.caching;
  console.log(
    `2. With Prompt Caching:                $${results.caching.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo ` +
    pc.green(`(Saved $${cacheSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | ${(cacheSaved / results.baseline * 100).toFixed(1)}%)`)
  );

  const batchSaved = results.baseline - results.batch;
  console.log(
    `3. With Asynchronous Batch API:        $${results.batch.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo ` +
    pc.green(`(Saved $${batchSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | 50.0%)`)
  );

  const combSaved = results.baseline - results.combined;
  console.log(
    `4. Combined (Batch + Prompt Caching):  $${results.combined.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo ` +
    pc.green(`(Saved $${combSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | ${(combSaved / results.baseline * 100).toFixed(1)}%)`)
  );

  const tierSaved = results.baseline - results.tiered;
  console.log(
    `5. Tiered Routing (80% to Economy):    $${results.tiered.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo ` +
    pc.green(`(Saved $${tierSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | ${(tierSaved / results.baseline * 100).toFixed(1)}%)`)
  );

  const gwSaved = results.baseline - results.gatewayFull;
  console.log(
    `6. Enterprise Gateway Architecture:    ` +
    pc.bold(pc.underline(`$${results.gatewayFull.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo `)) +
    pc.bold(pc.green(`(Saved $${gwSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | ${(gwSaved / results.baseline * 100).toFixed(1)}%)`))
  );

  console.log("--------------------------------------------------------------------------------");
  console.log(
    pc.bold(pc.green(`>>> Projected Annual Savings: $${(gwSaved * 12).toLocaleString(undefined, { minimumFractionDigits: 2 })} USD\n`))
  );
}

if (process.argv[1]?.includes("costCalculator")) {
  main();
}
