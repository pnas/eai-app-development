/**
 * Module 1: Streaming Comparison & SSE Chunk Mechanics (TypeScript)
 *
 * Demonstrates consuming Server-Sent Events (SSE) streams and capturing
 * usage metadata chunks across OpenAI, Anthropic, and Google Gemini.
 *
 * Official References:
 * - Anthropic Streaming: https://platform.claude.com/docs/en/build-with-claude/streaming
 * - Anthropic Working with Messages: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 * - Anthropic Effort Controls: https://platform.claude.com/docs/en/build-with-claude/effort
 * - OpenAI Streaming: https://platform.openai.com/docs/api-reference/chat/streaming
 * - Google Gemini Models: https://ai.google.dev/gemini-api/docs/models
 * - Google Gemini Streaming: https://ai.google.dev/gemini-api/docs/streaming
 * - Google Gemini Interactions API: https://ai.google.dev/gemini-api/docs/interactions-overview
 */

import pc from "picocolors";
import { getOpenAIClient, getAnthropicClient, getGeminiClient } from "./clientFactory.js";

async function streamOpenAI(prompt: string) {
  console.log(pc.cyan("\n=== Streaming OpenAI (gpt-4o-mini) ==="));
  const client = getOpenAIClient();

  const stream = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: prompt }],
    stream: true,
    stream_options: { include_usage: true },
  });

  let usage: any = null;
  for await (const chunk of stream) {
    const text = chunk.choices[0]?.delta?.content;
    if (text) {
      process.stdout.write(text);
    }
    if (chunk.usage) {
      usage = chunk.usage;
    }
  }

  console.log();
  if (usage) {
    console.log(pc.gray(`Usage: In=${usage.prompt_tokens}, Out=${usage.completion_tokens}, Total=${usage.total_tokens}`));
  }
}

async function streamAnthropic(prompt: string) {
  console.log(pc.magenta("\n=== Streaming Anthropic (claude-haiku-5-5) ==="));
  const client = getAnthropicClient();

  const stream = client.messages.stream({
    model: "claude-haiku-5-5",
    max_tokens: 512,
    messages: [{ role: "user", content: prompt }],
    ...( { output_config: { effort: "medium" } } as any ),
  });

  stream.on("streamEvent", (event: any) => {
    if (event.type === "content_block_delta") {
      if (event.delta?.type === "text_delta") {
        process.stdout.write(event.delta.text);
      } else if (event.delta?.type === "thinking_delta") {
        process.stdout.write(`[thinking: ${event.delta.thinking}]`);
      } else if (event.delta?.type === "signature_delta") {
        process.stdout.write("[sig]");
      }
    }
  });

  const finalMessage = await stream.finalMessage();
  console.log();
  console.log(
    pc.gray(`Usage: In=${finalMessage.usage.input_tokens}, Out=${finalMessage.usage.output_tokens}`)
  );
}

async function streamGemini(prompt: string) {
  console.log(pc.green("\n=== Streaming Google Gemini Content (gemini-3.8-flash) ===\n"));
  const client = getGeminiClient();

  const responseStream = await client.models.generateContentStream({
    model: "gemini-3.8-flash",
    contents: prompt,
  });

  let usage: any = null;
  for await (const chunk of responseStream) {
    if (chunk.text) {
      process.stdout.write(chunk.text);
    }
    if (chunk.usageMetadata) {
      usage = chunk.usageMetadata;
    }
  }

  console.log();
  if (usage) {
    console.log(pc.gray(`Usage: In=${usage.promptTokenCount}, Out=${usage.candidatesTokenCount}`));
  }
}

async function streamGeminiInteractions(prompt: string) {
  console.log(pc.green("\n=== Streaming Google Gemini Interactions API (gemini-3.8-flash) ===\n"));
  const client = getGeminiClient();

  const responseStream = await (client.interactions as any).create({
    model: "gemini-3.8-flash",
    input: prompt,
    generation_config: { thinking_summaries: "auto" },
    stream: true,
  });

  for await (const event of responseStream) {
    if (event.event_type === "step.start") {
      const stepType = event.step?.type;
      if (stepType === "thought") {
        process.stdout.write(pc.dim("[Thought Summary] "));
      }
    } else if (event.event_type === "step.delta") {
      const delta = event.delta;
      if (delta?.type === "thought_summary" && delta.content?.text) {
        process.stdout.write(delta.content.text);
      } else if (delta?.type === "text" || delta?.text) {
        process.stdout.write(delta.text || "");
      }
    }
  }
  console.log();
}

async function main() {
  const prompt = "In 2 sentences, explain why streaming reduces Time-To-First-Token (TTFT) for users.";
  try {
    await streamOpenAI(prompt);
  } catch (err: any) {
    console.log(pc.red(`OpenAI Stream Error: ${err.message}`));
  }

  try {
    await streamAnthropic(prompt);
  } catch (err: any) {
    console.log(pc.red(`Anthropic Stream Error: ${err.message}`));
  }

  try {
    await streamGemini(prompt);
  } catch (err: any) {
    console.log(pc.red(`Gemini Stream Error: ${err.message}`));
  }

  try {
    await streamGeminiInteractions(prompt);
  } catch (err: any) {
    console.log(pc.red(`Gemini Interactions Stream Error: ${err.message}`));
  }
}

main().catch(console.error);

