/**
 * Module 4: OpenAI Flex Processing Demo.
 *
 * Demonstrates Flex Processing (`service_tier: "flex"`) for synchronous, low-priority
 * batch and background workloads with a flat 50% discount on all token costs.
 *
 * Official References:
 * - Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
 * - Batch API: https://developers.openai.com/api/docs/guides/batch
 * - Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
 */

import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";

export interface FlexProcessingResult {
  id: string;
  model: string;
  serviceTier: string;
  latencySec: number;
  inputTokens: number;
  outputTokens: number;
  standardCost: number;
  flexCost: number;
  discountPercentage: number;
  content: string;
}

export async function runFlexProcessingRequest(options: {
  prompt: string;
  model?: string;
  timeoutMs?: number;
  useMockFallback?: boolean;
}): Promise<FlexProcessingResult> {
  const {
    prompt,
    model = "gpt-6-astra",
    timeoutMs = 900_000, // 15 minutes recommended
    useMockFallback = true,
  } = options;

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.startsWith("mock") || apiKey.startsWith("sk-placeholder")) {
    if (useMockFallback) {
      console.log("[Simulated Offline Mode] Executing synthetic Flex tier request...");
      return {
        id: "chatcmpl_mock_flex_ts_12345",
        model,
        serviceTier: "flex",
        latencySec: 3.82,
        inputTokens: 512,
        outputTokens: 128,
        standardCost: 0.000154,
        flexCost: 0.000077,
        discountPercentage: 50.0,
        content: "Root Cause Analysis: BGP flapping was triggered by optical interface CRC degradation on core router PE-04.",
      };
    }
    throw new Error("Missing or mock OPENAI_API_KEY.");
  }

  const client = getOpenAIClient();

  const t0 = performance.now();
  const response: any = await client.chat.completions.create(
    {
      model,
      messages: [
        { role: "system", content: "You are a telecom root cause analysis engine." },
        { role: "user", content: prompt },
      ],
      service_tier: "flex" as any,
    },
    { timeout: timeoutMs }
  );
  const latency = (performance.now() - t0) / 1000;

  const usage = response.usage;
  const inputTok = usage?.prompt_tokens ?? 0;
  const outputTok = usage?.completion_tokens ?? 0;

  const stdCost = (inputTok * 0.15 + outputTok * 0.60) / 1_000_000;
  const flexCost = stdCost * 0.50;

  return {
    id: response.id,
    model: response.model,
    serviceTier: response.service_tier || "flex",
    latencySec: Number(latency.toFixed(2)),
    inputTokens: inputTok,
    outputTokens: outputTok,
    standardCost: Number(stdCost.toFixed(6)),
    flexCost: Number(flexCost.toFixed(6)),
    discountPercentage: 50.0,
    content: response.choices[0]?.message?.content || "",
  };
}

export function compareBatchVsFlex(): void {
  console.log("\n=== OpenAI Asynchronous Batch API vs. Synchronous Flex Processing ===");
  console.table({
    "OpenAI Batch API": {
      "Invocation Model": "Asynchronous (.jsonl file upload + polling)",
      "Turnaround SLA": "Within 24 hours",
      "Cost Discount": "50% off all standard token rates",
      "API Parameter": "Endpoint: /v1/batches",
      "Supported Endpoints": "/v1/chat/completions, /v1/responses, /v1/embeddings",
      "Recommended Timeout": "N/A (Job polled asynchronously)",
      "Ideal Use Case": "Nightly 100K+ document embedding or offline audits",
    },
    "OpenAI Flex Processing": {
      "Invocation Model": "Synchronous (standard REST / SSE stream)",
      "Turnaround SLA": "Immediate (typically seconds to a few minutes)",
      "Cost Discount": "50% off all standard token rates",
      "API Parameter": "Parameter: service_tier='flex'",
      "Supported Endpoints": "Responses API & Chat Completions API",
      "Recommended Timeout": "15 minutes (900 seconds)",
      "Ideal Use Case": "Background tasks, ETL pipelines, non-urgent summaries",
    },
  });
}

async function main() {
  console.log("OpenAI Flex Processing Architecture (TypeScript)");
  const result = await runFlexProcessingRequest({
    prompt: "Analyze telemetry logs for 10 consecutive connection timeouts on edge gateway GW-09.",
    useMockFallback: true,
  });

  console.log(`Response ID: ${result.id}`);
  console.log(`Service Tier: ${result.serviceTier}`);
  console.log(`Latency: ${result.latencySec}s`);
  console.log(`Tokens: Input=${result.inputTokens}, Output=${result.outputTokens}`);
  console.log(`Standard Cost: $${result.standardCost} | Flex Cost (50% off): $${result.flexCost}`);
  console.log(`Summary Analysis: ${result.content}`);

  compareBatchVsFlex();
}

if (process.argv[1]?.includes("flexProcessingDemo")) {
  main().catch(console.error);
}
