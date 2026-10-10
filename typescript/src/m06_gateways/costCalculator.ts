import pc from "picocolors";

interface PricingModel {
  name: string;
  inputPerM: number;
  outputPerM: number;
  cacheReadPerM: number;
}

const PRICING: Record<string, PricingModel> = {
  "claude-3-5-sonnet": {
    name: "Claude 3.5 Sonnet",
    inputPerM: 3.0,
    outputPerM: 15.0,
    cacheReadPerM: 0.3, // 90% discount
  },
  "gpt-4o": {
    name: "OpenAI GPT-4o",
    inputPerM: 2.5,
    outputPerM: 10.0,
    cacheReadPerM: 1.25, // 50% discount
  },
};

function calculateMonthlySavings(
  pricing: PricingModel,
  monthlyRequests: number,
  staticPrefixTokens: number,
  dynamicInputTokens: number,
  outputTokens: number
) {
  const totalInputPerReq = staticPrefixTokens + dynamicInputTokens;

  // 1. Baseline: Uncached Realtime
  const baseInputCost = (monthlyRequests * totalInputPerReq / 1_000_000) * pricing.inputPerM;
  const baseOutputCost = (monthlyRequests * outputTokens / 1_000_000) * pricing.outputPerM;
  const baseline = baseInputCost + baseOutputCost;

  // 2. Realtime with Prompt Caching
  const cachedPrefixCost = (monthlyRequests * staticPrefixTokens / 1_000_000) * pricing.cacheReadPerM;
  const dynamicInCost = (monthlyRequests * dynamicInputTokens / 1_000_000) * pricing.inputPerM;
  const caching = cachedPrefixCost + dynamicInCost + baseOutputCost;

  // 3. Batch API (50% flat discount)
  const batch = baseline * 0.5;

  // 4. Combined: Batch + Prompt Caching
  const combined = caching * 0.5;

  return { baseline, caching, batch, combined };
}

function main() {
  console.log(pc.bold("\n=== Enterprise GenAI Cost Optimization ROI Model (TypeScript) ===\n"));

  const requests = 500_000;
  const prefixTok = 4_000;
  const dynamicTok = 500;
  const outputTok = 300;

  const modelKey = "claude-3-5-sonnet";
  const pricing = PRICING[modelKey];

  const results = calculateMonthlySavings(pricing, requests, prefixTok, dynamicTok, outputTok);

  console.log(pc.cyan(`Model: ${pricing.name} (Volume: ${requests.toLocaleString()} reqs/month)`));
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
    `4. Combined (Batch + Prompt Caching):  ` +
    pc.bold(pc.underline(`$${results.combined.toLocaleString(undefined, { minimumFractionDigits: 2 })} / mo `)) +
    pc.bold(pc.green(`(Saved $${combSaved.toLocaleString(undefined, { minimumFractionDigits: 2 })} | ${(combSaved / results.baseline * 100).toFixed(1)}%)`))
  );

  console.log("--------------------------------------------------------------------------------");
  console.log(
    pc.bold(pc.green(`>>> Projected Annual Savings: $${(combSaved * 12).toLocaleString(undefined, { minimumFractionDigits: 2 })} USD\n`))
  );
}

main();

