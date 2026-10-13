/**
 * Module 1: Cross-Provider Chat Completion Comparison (TypeScript)
 *
 * Demonstrates normalized schemas, roles, and reasoning token extraction
 * across OpenAI, Anthropic, and Google Gemini.
 *
 * Official References:
 * - OpenAI Chat API: https://platform.openai.com/docs/api-reference/chat
 * - Anthropic Messages API: https://docs.anthropic.com/en/api/messages
 * - Anthropic Extended Thinking: https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking
 * - Google GenAI TypeScript SDK: https://github.com/googleapis/genai-js
 * - Google Gemini Models: https://ai.google.dev/gemini-api/docs/models
 * - Google Gemini Streaming: https://ai.google.dev/gemini-api/docs/streaming
 * - Google Gemini Interactions API: https://ai.google.dev/gemini-api/docs/interactions-overview
 */

import pc from "picocolors";
import { getOpenAIClient, getAnthropicClient, getGeminiClient } from "./clientFactory.js";

interface NormalizedResponse {
  provider: string;
  model: string;
  content: string;
  promptTokens: number;
  completionTokens: number;
  reasoningTokens?: number;
  totalTokens: number;
}

async function callOpenAI(prompt: string, systemPrompt: string): Promise<NormalizedResponse> {
  const client = getOpenAIClient();
  const model = "gpt-4o-mini";

  const response = await client.chat.completions.create({
    model,
    messages: [
      { role: "developer", content: systemPrompt },
      { role: "user", content: prompt },
    ],
    temperature: 0.2,
  });

  const choice = response.choices[0];
  const usage = response.usage;
  const reasoningTokens = (usage as any)?.completion_tokens_details?.reasoning_tokens ?? 0;

  return {
    provider: "OpenAI",
    model,
    content: choice?.message?.content ?? "",
    promptTokens: usage?.prompt_tokens ?? 0,
    completionTokens: usage?.completion_tokens ?? 0,
    reasoningTokens,
    totalTokens: usage?.total_tokens ?? 0,
  };
}

async function callAnthropic(prompt: string, systemPrompt: string): Promise<NormalizedResponse> {
  const client = getAnthropicClient();
  const model = "claude-haiku-5-5";

  // NOTE: Claude 4.7+ and Claude 5.x do NOT accept temperature or top_p (HTTP 400).
  // Steer via prompt or output_config.effort.
  const response = await client.messages.create({
    model,
    system: systemPrompt,
    max_tokens: 1024,
    messages: [{ role: "user", content: prompt }],
    ...( { output_config: { effort: "medium" } } as any ),
  });

  let contentText = "";
  let reasoningTokens = 0;
  for (const block of response.content) {
    if (block.type === "text") {
      contentText += block.text;
    } else if ((block as any).type === "thinking") {
      const thinkingText = (block as any).thinking ?? "";
      reasoningTokens += thinkingText.split(/\s+/).filter(Boolean).length;
    }
  }

  return {
    provider: "Anthropic",
    model,
    content: contentText,
    promptTokens: response.usage.input_tokens,
    completionTokens: response.usage.output_tokens,
    reasoningTokens,
    totalTokens: response.usage.input_tokens + response.usage.output_tokens,
  };
}

async function callGemini(prompt: string, systemPrompt: string): Promise<NormalizedResponse> {
  const client = getGeminiClient();
  const model = "gemini-3.8-flash";

  const response = await client.models.generateContent({
    model,
    contents: prompt,
    config: {
      systemInstruction: systemPrompt,
      temperature: 0.2,
    },
  });

  const promptTok = response.usageMetadata?.promptTokenCount ?? 0;
  const compTok = response.usageMetadata?.candidatesTokenCount ?? 0;

  return {
    provider: "Google Gemini",
    model,
    content: response.text ?? "",
    promptTokens: promptTok,
    completionTokens: compTok,
    reasoningTokens: 0,
    totalTokens: promptTok + compTok,
  };
}

async function main() {
  const system = "You are a cloud systems architect. Answer in 2 succinct bullet points.";
  const query = "What are the primary differences between REST and gRPC in distributed microservices?";

  console.log(pc.bold("\n=== Cross-Provider Execution Benchmark (TypeScript) ===\n"));

  const callers = [
    { name: "OpenAI", fn: callOpenAI },
    { name: "Anthropic", fn: callAnthropic },
    { name: "Google Gemini", fn: callGemini },
  ];

  for (const { name, fn } of callers) {
    try {
      const res = await fn(query, system);
      console.log(
        pc.cyan(`[${res.provider}] `) +
        pc.magenta(`${res.model} `) +
        pc.green(`Tokens: In=${res.promptTokens}, Out=${res.completionTokens}, Reasoning=${res.reasoningTokens ?? 0}, Total=${res.totalTokens}`)
      );
      console.log(pc.white(res.content.trim()) + "\n");
    } catch (err: any) {
      console.log(pc.red(`[${name}] Failed: ${err?.message || err}\n`));
    }
  }
}

main().catch(console.error);

