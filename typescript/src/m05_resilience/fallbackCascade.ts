import pc from "picocolors";
import { CircuitBreaker, CircuitBreakerOpenException } from "./circuitBreaker.js";
import { getAnthropicClient, getOpenAIClient, getGeminiClient } from "../m01_paradigms/clientFactory.js";

interface ProviderNode {
  name: string;
  breaker: CircuitBreaker;
  invoke: (prompt: string) => Promise<string>;
}

class FallbackCascade {
  private providers: ProviderNode[];

  constructor(providers: ProviderNode[]) {
    this.providers = providers;
  }

  async execute(prompt: string): Promise<{ provider: string; result: string }> {
    const errorLog: string[] = [];

    for (const p of this.providers) {
      try {
        console.log(pc.cyan(`Routing to provider: ${p.name}...`));
        p.breaker.beforeCall();

        const result = await p.invoke(prompt);
        p.breaker.recordSuccess();
        return { provider: p.name, result };
      } catch (err: any) {
        if (err instanceof CircuitBreakerOpenException) {
          console.log(pc.yellow(`Skipping ${p.name}: Circuit breaker is OPEN.`));
          errorLog.push(`${p.name} (Breaker OPEN)`);
        } else {
          console.log(pc.red(`Provider ${p.name} failed: ${err.message}`));
          p.breaker.recordFailure(err);
          errorLog.push(`${p.name} (${err.name || "Error"})`);
        }
      }
    }

    throw new Error(`All providers in fallback cascade failed: ${errorLog.join(", ")}`);
  }
}

async function main() {
  console.log(pc.bold("\n=== Multi-Provider Fallback Cascade (TypeScript) ===\n"));

  const cascade = new FallbackCascade([
    {
      name: "Anthropic_Claude",
      breaker: new CircuitBreaker("Anthropic_Claude", 2, 10000),
      invoke: async (prompt) => {
        const client = getAnthropicClient();
        const res = await client.messages.create({
          model: "claude-3-5-haiku-20241022",
          max_tokens: 100,
          messages: [{ role: "user", content: prompt }],
        });
        const block = res.content.find((b) => b.type === "text") as any;
        return block?.text ?? "";
      },
    },
    {
      name: "OpenAI_GPT",
      breaker: new CircuitBreaker("OpenAI_GPT", 2, 10000),
      invoke: async (prompt) => {
        const client = getOpenAIClient();
        const res = await client.chat.completions.create({
          model: "gpt-4o-mini",
          max_tokens: 100,
          messages: [{ role: "user", content: prompt }],
        });
        return res.choices[0]?.message?.content ?? "";
      },
    },
    {
      name: "Google_Gemini",
      breaker: new CircuitBreaker("Google_Gemini", 2, 10000),
      invoke: async (prompt) => {
        const client = getGeminiClient();
        const res = await client.models.generateContent({
          model: "gemini-1.5-flash",
          contents: prompt,
        });
        return res.text ?? "";
      },
    },
  ]);

  const prompt = "Explain in one sentence why multi-provider failover guarantees high SLA.";

  try {
    const { provider, result } = await cascade.execute(prompt);
    console.log(pc.bold("\nSuccess via: ") + pc.green(provider));
    console.log(result.trim() + "\n");
  } catch (err: any) {
    console.log(pc.red(`Cascade exhausted: ${err.message}`));
  }
}

main().catch(console.error);

