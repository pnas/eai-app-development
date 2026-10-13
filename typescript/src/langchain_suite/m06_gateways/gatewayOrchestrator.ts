import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { ChatOpenAI } from "@langchain/openai";
import pc from "picocolors";
import { z } from "zod";
import dotenv from "dotenv";
import { AuditTelemetryHandler } from "../core/telemetry.js";

dotenv.config();

export const SubscriberDiagnosticSchema = z.object({
  subscriberId: z.string().describe("Unique customer subscriber ID (e.g. SUB-49-170...)"),
  planTier: z.string().describe("Subscription tier: PREPAID, POSTPAID_BASIC, ENTERPRISE_5G"),
  simStatus: z.enum(["ACTIVE", "SUSPENDED", "PENDING_PROVISION"]),
  recommendedAction: z.string().describe("Action to restore service"),
});

export type SubscriberDiagnostic = z.infer<typeof SubscriberDiagnosticSchema>;

export interface GatewayChatModelOptions {
  target?: "openrouter" | "litellm_proxy";
  modelName?: string;
  temperature?: number;
}

export function getGatewayChatModel(options: GatewayChatModelOptions = {}): ChatOpenAI {
  const target = options.target ?? "openrouter";
  const temperature = options.temperature ?? 0.0;

  if (target === "openrouter") {
    const apiKey = process.env.OPENROUTER_API_KEY || "mock-openrouter-key";
    const model = options.modelName ?? "anthropic/claude-3.5-haiku";
    return new ChatOpenAI({
      model,
      temperature,
      apiKey,
      configuration: {
        baseURL: "https://openrouter.ai/api/v1",
        defaultHeaders: {
          "HTTP-Referer": "https://telekom.com",
          "X-Title": "Telecom AI Gateway Suite (TS)",
        },
      },
    });
  } else if (target === "litellm_proxy") {
    const apiKey = process.env.LITELLM_VIRTUAL_KEY || "sk-virtual-telekom-billing";
    const baseURL = process.env.LITELLM_PROXY_URL || "http://localhost:4000/v1";
    const model = options.modelName ?? "enterprise-fast";
    return new ChatOpenAI({
      model,
      temperature,
      apiKey,
      configuration: {
        baseURL,
      },
    });
  } else {
    throw new Error(`Unknown gateway target: ${target}`);
  }
}

export async function runGatewayOrchestrationDemo(simulate = false) {
  console.log(pc.cyan(pc.bold("\n=== Module 6: LangChain Gateway Orchestration (TypeScript) ===\n")));

  const prompt = "Subscriber SUB-49-170-9821 on ENTERPRISE_5G has had SIM blocked due to roaming data ceiling threshold.";
  const hasOpenRouterKey = Boolean(process.env.OPENROUTER_API_KEY);

  if (simulate || !hasOpenRouterKey) {
    console.log(pc.yellow("OPENROUTER_API_KEY not found in .env. Running simulated structured extraction.\n"));
    const simulatedDiagnostic: SubscriberDiagnostic = {
      subscriberId: "SUB-49-170-9821",
      planTier: "ENTERPRISE_5G",
      simStatus: "SUSPENDED",
      recommendedAction: "Execute automated spend-limit reset after corporate admin authorization.",
    };

    console.log(pc.green("Structured Diagnostic (via simulated Gateway):"));
    console.log(pc.bold(`  Subscriber ID:      ${simulatedDiagnostic.subscriberId}`));
    console.log(pc.bold(`  Plan Tier:          ${simulatedDiagnostic.planTier}`));
    console.log(pc.bold(`  SIM Status:         ${pc.red(simulatedDiagnostic.simStatus)}`));
    console.log(pc.bold(`  Recommended Action: ${simulatedDiagnostic.recommendedAction}\n`));
    return simulatedDiagnostic;
  }

  // Live Gateway Pipeline
  const model = getGatewayChatModel({ target: "openrouter", modelName: "anthropic/claude-3.5-haiku" });
  const structuredModel = model.withStructuredOutput(SubscriberDiagnosticSchema);
  const telemetry = new AuditTelemetryHandler(false);

  console.log(pc.cyan("Executing structured output extraction via OpenRouter Gateway..."));
  const diagnostic = await structuredModel.invoke(
    [
      new SystemMessage("You are a telecom core network support agent. Extract diagnostics."),
      new HumanMessage(prompt),
    ],
    { callbacks: [telemetry] }
  );

  const summary = telemetry.getSummary();
  console.log(pc.green("\nLive Diagnostic Extracted via Gateway:"));
  console.log(pc.bold(`  Subscriber ID:      ${diagnostic.subscriberId}`));
  console.log(pc.bold(`  Plan Tier:          ${diagnostic.planTier}`));
  console.log(pc.bold(`  SIM Status:         ${diagnostic.simStatus}`));
  console.log(pc.bold(`  Recommended Action: ${diagnostic.recommendedAction}`));
  console.log(pc.magenta(`  Telemetry:          Tokens=${summary.totalTokens}, Duration=${summary.totalDurationSeconds.toFixed(2)}s\n`));

  return diagnostic;
}

if (process.argv[1]?.includes("gatewayOrchestrator")) {
  runGatewayOrchestrationDemo().catch(console.error);
}
