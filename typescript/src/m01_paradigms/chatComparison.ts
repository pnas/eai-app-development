import pc from "picocolors";
import { getOpenAIClient, getAnthropicClient, getGeminiClient } from "./clientFactory.js";

interface NormalizedResponse {
  provider: string;
  model: string;
  content: string;
  promptTokens: number;
  completionTokens: number;
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

  return {
    provider: "OpenAI",
    model,
    content: choice?.message?.content ?? "",
    promptTokens: usage?.prompt_tokens ?? 0,
    completionTokens: usage?.completion_tokens ?? 0,
    totalTokens: usage?.total_tokens ?? 0,
  };
}

async function callAnthropic(prompt: string, systemPrompt: string): Promise<NormalizedResponse> {
  const client = getAnthropicClient();
  const model = "claude-3-5-haiku-20241022";

  const response = await client.messages.create({
    model,
    system: systemPrompt,
    max_tokens: 1024,
    messages: [{ role: "user", content: prompt }],
    temperature: 0.2,
  });

  const contentText = response.content
    .filter((b) => b.type === "text")
    .map((b) => (b as { type: "text"; text: string }).text)
    .join("");

  return {
    provider: "Anthropic",
    model,
    content: contentText,
    promptTokens: response.usage.input_tokens,
    completionTokens: response.usage.output_tokens,
    totalTokens: response.usage.input_tokens + response.usage.output_tokens,
  };
}

async function callGemini(prompt: string, systemPrompt: string): Promise<NormalizedResponse> {
  const client = getGeminiClient();
  const model = "gemini-1.5-flash";

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
        pc.green(`Tokens: In=${res.promptTokens}, Out=${res.completionTokens}, Total=${res.totalTokens}`)
      );
      console.log(pc.white(res.content.trim()) + "\n");
    } catch (err: any) {
      console.log(pc.red(`[${name}] Failed: ${err?.message || err}\n`));
    }
  }
}

main().catch(console.error);

