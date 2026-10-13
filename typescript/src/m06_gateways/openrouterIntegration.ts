import pc from "picocolors";
import { getOpenRouterClient } from "../m01_paradigms/clientFactory.js";

export interface OpenRouterPayloadOptions {
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  primaryModel?: string;
  fallbackModels?: string[];
  denyDataCollection?: boolean;
  responseFormat?: Record<string, unknown>;
}

export function buildOpenRouterPayload(options: OpenRouterPayloadOptions) {
  const primaryModel = options.primaryModel ?? "anthropic/claude-3.5-haiku";
  const fallbackModels = options.fallbackModels ?? ["openai/gpt-4o-mini", "google/gemini-flash-1.5"];
  const allModels = [primaryModel, ...fallbackModels.filter((m) => m !== primaryModel)];

  const extraBody: Record<string, unknown> = {
    models: allModels,
    route: "fallback",
    provider: {
      order: ["Anthropic", "Google", "OpenAI"],
      allow_fallbacks: true,
      data_collection: options.denyDataCollection !== false ? "deny" : "allow",
      require_parameters: true,
    },
  };

  const payload: Record<string, unknown> = {
    model: primaryModel,
    messages: options.messages,
    extra_body: extraBody,
  };

  if (options.responseFormat) {
    payload.response_format = options.responseFormat;
  }

  return payload;
}

export function generateOpenRouterBatchSpec() {
  return {
    endpoint: "/v1/chat/completions",
    model: "anthropic/claude-3.5-haiku",
    requests: [
      {
        custom_id: "req-telecom-ts-001",
        body: {
          messages: [{ role: "user", content: "Summarize BSS CDR invoice anomaly #991" }],
          max_tokens: 100,
        },
      },
      {
        custom_id: "req-telecom-ts-002",
        body: {
          messages: [{ role: "user", content: "Summarize BSS CDR invoice anomaly #992" }],
          max_tokens: 100,
        },
      },
    ],
    provider: {
      data_collection: "deny",
    },
  };
}

export async function runOpenRouterDemo() {
  console.log(pc.magenta(pc.bold("\n=== OpenRouter Multi-Provider Auto-Routing & Privacy Controls (TypeScript) ===\n")));

  const prompt = "Explain how multi-provider fallback cascades prevent downtime during regional cloud outages.";

  if (!process.env.OPENROUTER_API_KEY) {
    console.log(pc.yellow("OPENROUTER_API_KEY not found in .env. Running simulated dynamic routing."));
    const simulated = {
      model: "anthropic/claude-3.5-haiku (simulated)",
      response: "[Simulated OpenRouter TS] Cascading across Anthropic -> Google -> OpenAI prevents service interruption when an individual cluster returns 429 or 503.",
      inputTokens: 52,
      outputTokens: 28,
      cachedTokens: 32,
      provider: "Anthropic",
      dataCollection: "DENIED",
    };

    console.log(pc.cyan(`Selected Model: ${simulated.model}`));
    console.log(pc.green(`Tokens: Input=${simulated.inputTokens}, Cached=${simulated.cachedTokens}, Output=${simulated.outputTokens}`));
    console.log(pc.bold(`Privacy Policy: data_collection = ${simulated.dataCollection}`));
    console.log(`Response:\n${simulated.response}\n`);

    console.log(pc.yellow("Batch API Blueprint (50% Off Asynchronous Jobs):"));
    const spec = generateOpenRouterBatchSpec();
    console.log(`Endpoint: POST https://openrouter.ai/api/v1/batches`);
    console.log(`Model: ${spec.model} | Batched Requests: ${spec.requests.length} | Privacy: ${spec.provider.data_collection}\n`);
    return simulated;
  }

  const client = getOpenRouterClient();
  const payload = buildOpenRouterPayload({
    messages: [{ role: "user", content: prompt }],
    primaryModel: "anthropic/claude-3.5-haiku",
  });

  const response = await client.chat.completions.create(payload as any);
  const choice = response.choices[0];
  const usage = response.usage;
  const cachedTokens = (usage as any)?.prompt_tokens_details?.cached_tokens ?? 0;

  console.log(pc.cyan(`Selected Model: ${response.model}`));
  console.log(pc.green(`Tokens: Input=${usage?.prompt_tokens}, Cached=${cachedTokens}, Output=${usage?.completion_tokens}`));
  console.log(`Response:\n${choice?.message?.content}\n`);

  return {
    model: response.model,
    content: choice?.message?.content,
    usage,
  };
}

if (process.argv[1]?.includes("openrouterIntegration")) {
  runOpenRouterDemo().catch(console.error);
}
