/**
 * Module 1: OpenAI Responses API & Reasoning Models Demo.
 *
 * Demonstrates the Responses API (`client.responses.create`) with reasoning models
 * (gpt-6.1-sol, gpt-6-astra), reasoning effort controls, commentary streaming,
 * fast mode (`service_tier: "fast"`), and explicit caching options.
 *
 * Official References:
 * - Latency Optimization: https://developers.openai.com/api/docs/guides/latency-optimization
 * - Fast Mode: https://developers.openai.com/api/docs/guides/fast-mode
 * - Prompt Caching: https://developers.openai.com/api/docs/guides/prompt-caching
 * - Rate Limits: https://developers.openai.com/api/docs/guides/rate-limits
 * - Flex Processing: https://developers.openai.com/api/docs/guides/flex-processing
 */

import { getOpenAIClient } from "./clientFactory.js";

export interface NormalizedReasoningResult {
  id: string;
  model: string;
  serviceTier: string;
  reasoningEffort: string;
  reasoningSummary: string;
  outputText: string;
  usage: {
    inputTokens: number;
    outputTokens: number;
    reasoningTokens: number;
    cachedTokens: number;
  };
}

export async function runReasoningResponse(options: {
  prompt: string;
  instructions?: string;
  model?: string;
  effort?: "low" | "medium" | "high";
  serviceTier?: "default" | "fast" | "flex" | "auto";
  useMockFallback?: boolean;
}): Promise<NormalizedReasoningResult> {
  const {
    prompt,
    instructions = "You are a telecom network optimization architect.",
    model = "gpt-6.1-sol",
    effort = "high",
    serviceTier = "default",
    useMockFallback = true,
  } = options;

  console.log(`\n=== OpenAI Responses API: ${model} (service_tier=${serviceTier}, effort=${effort}) ===`);

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.startsWith("mock") || apiKey.startsWith("sk-placeholder")) {
    if (useMockFallback) {
      console.log("[Simulated Offline Mode] Returning synthetic reasoning and answer response...");
      return {
        id: "resp_mock_61sol_ts_987654",
        model,
        serviceTier,
        reasoningEffort: effort,
        reasoningSummary: `Evaluated 5G core slicing latency constraints. Analyzed jitter buffer and URLLC QoS parameters under ${effort} effort.`,
        outputText: "Optimal configuration: Allocate dedicated network slice ID 0x01 with 15kHz subcarrier spacing and enable pre-emptive dynamic BWP switching.",
        usage: {
          inputTokens: 1420,
          outputTokens: 380,
          reasoningTokens: 260,
          cachedTokens: 1024,
        },
      };
    }
    throw new Error("Missing or mock OPENAI_API_KEY environment variable.");
  }

  const client = getOpenAIClient();

  const response: any = await (client.responses as any).create({
    model,
    instructions,
    input: prompt,
    reasoning: { effort, summary: "auto" },
    service_tier: serviceTier,
    prompt_cache_options: { mode: "explicit" },
  });

  let outputText = "";
  let reasoningSummary = "";

  function extractTextContent(contentData: any): string {
    if (!contentData) return "";
    if (typeof contentData === "string") return contentData;
    if (Array.isArray(contentData)) {
      return contentData
        .map((part) => {
          if (typeof part === "string") return part;
          if (part && typeof part === "object") return part.text ?? "";
          return "";
        })
        .join("");
    }
    if (typeof contentData === "object" && contentData.text) {
      return contentData.text;
    }
    return "";
  }

  if (response.output && Array.isArray(response.output)) {
    for (const item of response.output) {
      if (item.type === "message" && Array.isArray(item.content)) {
        for (const part of item.content) {
          if (part.type === "text" || part.type === "output_text" || part.text) {
            outputText += part.text ?? "";
          }
        }
      } else if (item.type === "reasoning") {
        const summaryText = extractTextContent(item.summary);
        if (summaryText) {
          reasoningSummary += summaryText;
        } else {
          // Fallback to reasoning content if summary is empty
          reasoningSummary += extractTextContent(item.content);
        }
      }
    }
  }

  // Fallback to response.output_text property if available and not yet set
  if (!outputText && typeof response.output_text === "string") {
    outputText = response.output_text;
  }

  const usage = response.usage;
  return {
    id: response.id || "",
    model: response.model || model,
    serviceTier,
    reasoningEffort: effort,
    reasoningSummary,
    outputText,
    usage: {
      inputTokens: usage?.input_tokens ?? 0,
      outputTokens: usage?.output_tokens ?? 0,
      reasoningTokens: usage?.output_tokens_details?.reasoning_tokens ?? 0,
      cachedTokens: usage?.input_tokens_details?.cached_tokens ?? 0,
    },
  };
}

export async function streamReasoningResponse(
  prompt: string,
  model = "gpt-6.1-sol",
  useMockFallback = true
): Promise<void> {
  console.log(`\n=== Streaming Responses API (${model}) ===`);

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey || apiKey.startsWith("mock") || apiKey.startsWith("sk-placeholder")) {
    if (useMockFallback) {
      console.log("[Simulated Streaming]");
      console.log("[Reasoning Phase] Analyzing routing graph and BGP route-reflector topologies...");
      await new Promise((resolve) => setTimeout(resolve, 50));
      console.log("Answer: Apply AS-Path prepending and Local Preference 200 on primary transit links to steer outbound traffic.");
      return;
    }
    throw new Error("Missing or mock OPENAI_API_KEY.");
  }

  const client = getOpenAIClient();
  const stream: any = await (client.responses as any).create({
    model,
    instructions: "Analyze telecommunications routing policies.",
    input: prompt,
    reasoning: { effort: "high", summary: "auto" },
    stream: true,
  });

  process.stdout.write("Streaming event stream: ");
  for await (const event of stream) {
    const eventType = event.type || "";
    const delta = typeof event.delta === "string" ? event.delta : event.delta?.text || "";
    if (!delta) continue;
    if (eventType.includes("reasoning")) {
      process.stdout.write(`[thought: ${delta}]`);
    } else if (eventType.includes("output") || eventType.includes("text")) {
      process.stdout.write(delta);
    }
  }
  console.log();
}

async function main() {
  console.log("OpenAI Responses API & Reasoning Architecture (TypeScript)");
  const result = await runReasoningResponse({
    prompt: "Design a failover routing policy between Frankfurt and Munich 5G data centers.",
    effort: "high",
    serviceTier: "fast",
    useMockFallback: true,
  });

  console.log(`Reasoning Summary: ${result.reasoningSummary}`);
  console.log(`Output Answer: ${result.outputText}`);
  console.log("Tokens:", result.usage);

  await streamReasoningResponse(
    "Explain latency implications of explicit prompt cache breakpoints.",
    "gpt-6.1-sol",
    true
  );
}

if (process.argv[1]?.includes("responsesReasoningDemo")) {
  main().catch(console.error);
}
