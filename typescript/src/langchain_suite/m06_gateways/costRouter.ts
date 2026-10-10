import { HumanMessage } from "@langchain/core/messages";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";
import { AuditTelemetryHandler } from "../core/telemetry.js";

const PRICING = {
  "gpt-4o-mini": { input: 0.15, output: 0.60 },
  "gpt-4o": { input: 2.50, output: 10.00 },
};

function estimateCost(model: "gpt-4o-mini" | "gpt-4o", tokens: number): number {
  const rate = PRICING[model] ?? PRICING["gpt-4o-mini"];
  return (tokens / 1_000_000) * ((rate.input + rate.output) / 2);
}

async function routeAndExecute(prompt: string) {
  const complexKeywords = ["architecture", "optimize", "rfc", "root cause", "capacity"];
  const isComplex = complexKeywords.some((kw) => prompt.toLowerCase().includes(kw)) || prompt.split(" ").length > 25;

  const modelName = isComplex ? "gpt-4o" : "gpt-4o-mini";
  const model = getChatModel("openai", { model: modelName, temperature: 0 });

  const telemetry = new AuditTelemetryHandler(false);
  const response = await model.invoke([new HumanMessage(prompt)], {
    callbacks: [telemetry],
  });

  const summary = telemetry.getSummary();
  const cost = estimateCost(modelName as "gpt-4o-mini" | "gpt-4o", summary.totalTokens);

  return {
    query: prompt.slice(0, 45) + "...",
    tier: isComplex ? "HIGH-REASONING" : "FAST-ECONOMY",
    model: modelName,
    tokens: summary.totalTokens,
    costUsd: `$${cost.toFixed(6)}`,
  };
}

async function runCostRouterDemo() {
  console.log(pc.yellow("\n=== Module 6 (TypeScript): Dynamic Model Routing & Unit Economics ===\n"));

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

