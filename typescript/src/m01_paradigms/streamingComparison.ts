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
  console.log(pc.magenta("\n=== Streaming Anthropic (claude-3-5-haiku) ==="));
  const client = getAnthropicClient();

  const stream = client.messages.stream({
    model: "claude-3-5-haiku-20241022",
    max_tokens: 512,
    messages: [{ role: "user", content: prompt }],
  });

  stream.on("text", (text) => {
    process.stdout.write(text);
  });

  const finalMessage = await stream.finalMessage();
  console.log();
  console.log(
    pc.gray(`Usage: In=${finalMessage.usage.input_tokens}, Out=${finalMessage.usage.output_tokens}`)
  );
}

async function streamGemini(prompt: string) {
  console.log(pc.green("\n=== Streaming Google Gemini (gemini-1.5-flash) ==="));
  const client = getGeminiClient();

  const responseStream = await client.models.generateContentStream({
    model: "gemini-1.5-flash",
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
}

main().catch(console.error);

