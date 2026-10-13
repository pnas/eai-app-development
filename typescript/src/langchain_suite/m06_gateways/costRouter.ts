import { HumanMessage } from "@langchain/core/messages";
import pc from "picocolors";
import { z } from "zod";
import { getChatModel } from "../core/models.js";
import { AuditTelemetryHandler } from "../core/telemetry.js";

const PRICING: Record<string, { input: number; output: number }> = {
  "gpt-4o-mini": { input: 0.15, output: 0.60 },
  "gpt-4o": { input: 2.50, output: 10.00 },
  "gpt-4.1-mini": { input: 0.20, output: 0.80 },
  "gpt-4.1": { input: 2.00, output: 8.00 },
  "gpt-6-luna": { input: 2.00, output: 8.00 },
  "gpt-6-astra": { input: 3.00, output: 12.00 },
};

export const RoutingDecisionSchema = z.object({
  querySummary: z.string().describe("Brief 5-word summary of the query"),
  complexityTier: z.enum(["FAST-ECONOMY", "HIGH-REASONING"]),
  selectedModel: z.string(),
  reasoning: z.string(),
});

export type RoutingDecision = z.infer<typeof RoutingDecisionSchema>;

export function estimateCost(model: string, tokens: number): number {
  const rate = PRICING[model] ?? PRICING["gpt-4.1-mini"];
  return (tokens / 1_000_000) * ((rate.input + rate.output) / 2);
}

export async function routeAndExecute(prompt: string, simulate = false) {
  const complexKeywords = ["architecture", "optimize", "rfc", "root cause", "capacity", "distributed", "migration"];
  const isComplex = complexKeywords.some((kw) => prompt.toLowerCase().includes(kw)) || prompt.split(" ").length > 25;

  const modelName = isComplex ? "gpt-4.1" : "gpt-4.1-mini";
  const fallbackModelName = isComplex ? "gpt-4.1-mini" : "gpt-4.1";

  if (simulate || !process.env.OPENAI_API_KEY) {
    const simTokens = isComplex ? 65 : 30;
    const cost = estimateCost(modelName, simTokens);
    return {
      query: prompt.slice(0, 45) + "...",
      tier: isComplex ? "HIGH-REASONING" : "FAST-ECONOMY",
      model: modelName,
      tokens: simTokens,
      costUsd: `$${cost.toFixed(6)}`,
    };
  }

  const primaryModel = getChatModel("openai", { model: modelName, temperature: 0 });
  const backupModel = getChatModel("openai", { model: fallbackModelName, temperature: 0 });

  // Attach resilience fallback cascade
  const resilientChain = primaryModel.withFallbacks([backupModel]);

  const telemetry = new AuditTelemetryHandler(false);
  await resilientChain.invoke([new HumanMessage(prompt)], {
    callbacks: [telemetry],
  });

  const summary = telemetry.getSummary();
  const cost = estimateCost(modelName, summary.totalTokens);

  return {
    query: prompt.slice(0, 45) + "...",
    tier: isComplex ? "HIGH-REASONING" : "FAST-ECONOMY",
    model: modelName,
    tokens: summary.totalTokens,
    costUsd: `$${cost.toFixed(6)}`,
  };
}

export async function runCostRouterDemo() {
  console.log(pc.yellow("\n=== Module 6 (TypeScript): Dynamic Model Routing & Fallback Cascades ===\n"));

  const queries = [
    "What is the function of the AMF in the 5G Core?",
    "Design a zero-downtime distributed migration strategy for 20 million subscriber HLR records to cloud-native UDM.",
    "List the frequency bands for LTE Band 20.",
  ];

  for (const q of queries) {
    const result = await routeAndExecute(q);
    console.log(
      pc.cyan(`[${result.tier}]`),
      pc.yellow(`Model: ${result.model}`),
      pc.magenta(`Tokens: ${result.tokens}`),
      pc.green(`Cost: ${result.costUsd}`),
      `\n  Query: "${result.query}"`
    );
  }
}

if (process.argv[1]?.includes("costRouter")) {
  runCostRouterDemo().catch(console.error);
}
