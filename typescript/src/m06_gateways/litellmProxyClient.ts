import OpenAI from "openai";
import pc from "picocolors";
import dotenv from "dotenv";

dotenv.config();

export interface LiteLLMProxyOptions {
  proxyUrl?: string;
  virtualKey?: string;
}

export function getLiteLLMProxyClient(options?: LiteLLMProxyOptions): OpenAI {
  const baseURL = options?.proxyUrl || process.env.LITELLM_PROXY_URL || "http://localhost:4000/v1";
  const apiKey = options?.virtualKey || process.env.LITELLM_VIRTUAL_KEY || "sk-virtual-telekom-billing";

  return new OpenAI({
    baseURL,
    apiKey,
  });
}

export async function runLiteLLMProxyDemo() {
  console.log(pc.cyan(pc.bold("\n=== LiteLLM Proxy Virtual Key Client (TypeScript) ===\n")));

  const client = getLiteLLMProxyClient();
  const prompt = "Explain why enterprise organizations enforce virtual keys with spend caps at the gateway layer.";

  const hasLiveProxy = Boolean(process.env.LITELLM_PROXY_URL);

  if (!hasLiveProxy) {
    console.log(pc.yellow("LITELLM_PROXY_URL not set. Running simulated LiteLLM Proxy interaction."));
    const simulated = {
      model: "enterprise-reasoning (routed to Claude 3.5 Sonnet)",
      virtualKey: "sk-virtual-telekom-billing",
      budgetRemaining: "$482.40 / $500.00",
      content: "[Simulated LiteLLM Proxy] Virtual keys prevent credential leakage and enforce token-bucket rate limits and hard spend caps per team.",
      tokens: { prompt: 44, completion: 22, total: 66 },
      cacheHit: false,
    };

    console.log(pc.magenta(`Virtual Key: ${simulated.virtualKey} (Remaining: ${simulated.budgetRemaining})`));
    console.log(pc.green(`Model: ${simulated.model}`));
    console.log(pc.cyan(`Tokens: ${simulated.tokens.total}`));
    console.log(`Response:\n${simulated.content}\n`);
    return simulated;
  }

  try {
    const response = await client.chat.completions.create({
      model: "enterprise-reasoning",
      messages: [{ role: "user", content: prompt }],
      max_tokens: 150,
    });

    console.log(pc.green(`Model: ${response.model}`));
    console.log(`Response:\n${response.choices[0]?.message?.content}\n`);
    return response;
  } catch (error) {
    console.error(pc.red(`LiteLLM Proxy request failed: ${error}`));
  }
}

if (process.argv[1]?.includes("litellmProxyClient")) {
  runLiteLLMProxyDemo().catch(console.error);
}
