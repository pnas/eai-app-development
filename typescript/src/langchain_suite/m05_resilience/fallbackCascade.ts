import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatResult } from "@langchain/core/outputs";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";

export class FailingMockModel extends BaseChatModel {
  _llmType(): string {
    return "failing_mock";
  }
  async _generate(): Promise<ChatResult> {
    const error: any = new Error("HTTP 529: Provider Overloaded. Capacity exceeded.");
    error.status = 529;
    throw error;
  }
}

export class HealthyMockModel extends BaseChatModel {
  providerName: string;

  constructor(providerName = "backup-provider") {
    super({});
    this.providerName = providerName;
  }

  _llmType(): string {
    return "healthy_mock";
  }

  async _generate(): Promise<ChatResult> {
    const content = `[Served by ${this.providerName}] 5G NSA (Non-Standalone) anchors control plane signaling on legacy 4G LTE EPC, while 5G SA (Standalone) operates with a cloud-native 5G Core (5GC) enabling pure end-to-end network slicing.`;
    return {
      generations: [
        {
          text: content,
          message: new AIMessage({
            content,
            response_metadata: { model_name: this.providerName },
          }),
        },
      ],
    };
  }
}

export async function demonstrateFallbackCascade(simulateFailure = true) {
  console.log(pc.yellow("\n=== Module 5 (TypeScript): Multi-Provider Fallback Cascade ===\n"));

  let primary: BaseChatModel;
  let secondary: BaseChatModel;
  let tertiary: BaseChatModel;

  if (simulateFailure) {
    primary = new FailingMockModel({});
    secondary = new HealthyMockModel("gpt-4.1-mini (Secondary Fallback)");
    tertiary = new HealthyMockModel("gemini-3.8-flash (Tertiary Fallback)");
  } else {
    try {
      primary = getChatModel("anthropic", { model: "claude-haiku-5-5" });
    } catch {
      primary = new FailingMockModel({});
    }

    try {
      secondary = getChatModel("openai", { model: "gpt-4.1-mini" });
    } catch {
      secondary = new HealthyMockModel("gpt-4.1-mini (Secondary Fallback)");
    }

    try {
      tertiary = getChatModel("gemini", { model: "gemini-3.8-flash" });
    } catch {
      tertiary = new HealthyMockModel("gemini-3.8-flash (Tertiary Fallback)");
    }
  }

  const resilientChain = primary.withFallbacks({
    fallbacks: [secondary, tertiary],
  });

  const query = "Summarize the architectural difference between Non-Standalone (NSA) and Standalone (SA) 5G.";
  console.log(pc.cyan(`Executing query: "${query}"`));

  try {
    const response = await resilientChain.invoke([new HumanMessage(query)]);
    console.log(pc.green("✅ Request Recovered Successfully via Fallback!"));
    console.log("Response Preview:", String(response.content).slice(0, 150) + "...\n");
  } catch (err: any) {
    console.log(pc.red(`❌ Cascade failed: ${err.message}`));
  }
}

if (process.argv[1]?.includes("fallbackCascade")) {
  demonstrateFallbackCascade(true).catch(console.error);
}


