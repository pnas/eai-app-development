import { HumanMessage } from "@langchain/core/messages";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatResult } from "@langchain/core/outputs";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";

class FailingMockModel extends BaseChatModel {
  _llmType(): string {
    return "failing_mock";
  }
  async _generate(): Promise<ChatResult> {
    const error: any = new Error("HTTP 529: Provider Overloaded. Capacity exceeded.");
    error.status = 529;
    throw error;
  }
}

async function demonstrateFallbackCascade(simulateFailure = true) {
  console.log(pc.yellow("\n=== Module 5 (TypeScript): Multi-Provider Fallback Cascade ===\n"));

  const primary = simulateFailure
    ? new FailingMockModel({})
    : getChatModel("anthropic");

  const secondary = getChatModel("openai");
  const tertiary = getChatModel("gemini");

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

