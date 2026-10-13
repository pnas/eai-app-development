/**
 * Module 2: OpenAI Predicted Outputs & Speculative Decoding Demo.
 *
 * Demonstrates speculative decoding using Predicted Outputs (`prediction: { type: "content", content: "..." }`)
 * to accelerate code refactoring and structured edits by 2x to 4x.
 *
 * Official References:
 * - Predicted Outputs: https://developers.openai.com/api/docs/guides/predicted-outputs
 * - Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
 */

import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";

export const SAMPLE_ORIGINAL_CODE = `function calculateSlaUptime(downtimeMinutes: number, totalMinutes: number = 43200): number {
  if (totalMinutes <= 0) return 0;
  const uptimeMinutes = totalMinutes - downtimeMinutes;
  return (uptimeMinutes / totalMinutes) * 100.0;
}
`;

export const SAMPLE_PROMPT = `Refactor this TypeScript function to add JSDoc documentation, parameter validation, and throw an Error if downtimeMinutes is negative:

\`\`\`typescript
function calculateSlaUptime(downtimeMinutes: number, totalMinutes: number = 43200): number {
  if (totalMinutes <= 0) return 0;
  const uptimeMinutes = totalMinutes - downtimeMinutes;
  return (uptimeMinutes / totalMinutes) * 100.0;
}
\`\`\`
`;

export interface BenchmarkMetrics {
  standard: {
    latencySec: number;
    completionTokens: number;
    acceptedPredictionTokens: number;
    rejectedPredictionTokens: number;
    result: string;
  };
  speculative: {
    latencySec: number;
    completionTokens: number;
    acceptedPredictionTokens: number;
    rejectedPredictionTokens: number;
    result: string;
  };
  speedupFactor: number;
  tokenAcceptanceRate: number;
}

export async function benchmarkPredictedOutputs(options: {
  originalCode?: string;
  prompt?: string;
  model?: string;
  useMockFallback?: boolean;
} = {}): Promise<BenchmarkMetrics> {
  const {
    originalCode = SAMPLE_ORIGINAL_CODE,
    prompt = SAMPLE_PROMPT,
    model = "gpt-4.1-mini",
    useMockFallback = true,
  } = options;

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.startsWith("mock") || apiKey.startsWith("sk-placeholder")) {
    if (useMockFallback) {
      console.log("[Simulated Offline Benchmark] Measuring speculative decoding savings...");
      return {
        standard: {
          latencySec: 1.45,
          completionTokens: 135,
          acceptedPredictionTokens: 0,
          rejectedPredictionTokens: 0,
          result: `/**\n * Calculates SLA uptime percentage.\n */\nfunction calculateSlaUptime...`,
        },
        speculative: {
          latencySec: 0.39,
          completionTokens: 135,
          acceptedPredictionTokens: 104,
          rejectedPredictionTokens: 11,
          result: `/**\n * Calculates SLA uptime percentage.\n */\nfunction calculateSlaUptime...`,
        },
        speedupFactor: 3.72,
        tokenAcceptanceRate: 90.4,
      };
    }
    throw new Error("Missing or mock OPENAI_API_KEY environment variable.");
  }

  const client = getOpenAIClient();

  // 1. Standard Generation (Baseline)
  const t0Standard = performance.now();
  const resStandard = await client.chat.completions.create({
    model,
    messages: [
      { role: "system", content: "You are an expert TypeScript engineer. Output only updated code." },
      { role: "user", content: prompt },
    ],
    temperature: 0,
  });
  const tStandard = (performance.now() - t0Standard) / 1000;

  // 2. Speculative Generation with Predicted Outputs
  const t0Speculative = performance.now();
  const resPredicted = await client.chat.completions.create({
    model,
    messages: [
      { role: "system", content: "You are an expert TypeScript engineer. Output only updated code." },
      { role: "user", content: prompt },
    ],
    prediction: { type: "content", content: originalCode },
    temperature: 0,
  });
  const tSpeculative = (performance.now() - t0Speculative) / 1000;

  const usageStd = resStandard.usage;
  const usagePred = resPredicted.usage;
  const predDetails = (usagePred as any)?.completion_tokens_details;
  const accepted = predDetails?.accepted_prediction_tokens ?? 0;
  const rejected = predDetails?.rejected_prediction_tokens ?? 0;

  const totalPred = accepted + rejected;
  const acceptanceRate = totalPred > 0 ? (accepted / totalPred) * 100 : 0;
  const speedup = tSpeculative > 0 ? tStandard / tSpeculative : 1.0;

  return {
    standard: {
      latencySec: Number(tStandard.toFixed(3)),
      completionTokens: usageStd?.completion_tokens ?? 0,
      acceptedPredictionTokens: 0,
      rejectedPredictionTokens: 0,
      result: resStandard.choices[0]?.message?.content ?? "",
    },
    speculative: {
      latencySec: Number(tSpeculative.toFixed(3)),
      completionTokens: usagePred?.completion_tokens ?? 0,
      acceptedPredictionTokens: accepted,
      rejectedPredictionTokens: rejected,
      result: resPredicted.choices[0]?.message?.content ?? "",
    },
    speedupFactor: Number(speedup.toFixed(2)),
    tokenAcceptanceRate: Number(acceptanceRate.toFixed(1)),
  };
}

async function main() {
  console.log("\n=== OpenAI Predicted Outputs & Speculative Decoding Benchmark (TypeScript) ===");
  const data = await benchmarkPredictedOutputs({ useMockFallback: true });

  console.table({
    "Standard Generation": {
      "Latency (s)": `${data.standard.latencySec}s`,
      "Speedup": "1.0x (Baseline)",
      "Tokens": data.standard.completionTokens,
      "Accepted Predictions": data.standard.acceptedPredictionTokens,
      "Rejected Predictions": data.standard.rejectedPredictionTokens,
    },
    "Predicted Outputs (Speculative)": {
      "Latency (s)": `${data.speculative.latencySec}s`,
      "Speedup": `${data.speedupFactor}x Faster`,
      "Tokens": data.speculative.completionTokens,
      "Accepted Predictions": data.speculative.acceptedPredictionTokens,
      "Rejected Predictions": data.speculative.rejectedPredictionTokens,
    },
  });

  console.log(`Token Acceptance Ratio: ${data.tokenAcceptanceRate}%`);
}

if (process.argv[1]?.includes("predictedOutputsDemo")) {
  main().catch(console.error);
}
