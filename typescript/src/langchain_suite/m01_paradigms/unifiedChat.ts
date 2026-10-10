import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";
import { AuditTelemetryHandler } from "../core/telemetry.js";

async function compareUnifiedChat(prompt: string, systemPrompt: string) {
  const providers: Array<"openai" | "anthropic" | "gemini"> = ["openai", "anthropic", "gemini"];
  const telemetry = new AuditTelemetryHandler(false);

  console.log(pc.yellow("\n=== Module 1 (TypeScript): Unified Chat Invocation & Streaming ===\n"));

  for (const provider of providers) {
    console.log(pc.cyan(`Invoking ${provider.toUpperCase()} with normalized messages...`));
    try {
      const model = getChatModel(provider, { temperature: 0.1 });
      const messages = [
        new SystemMessage(systemPrompt),
        new HumanMessage(prompt),
      ];

      process.stdout.write(`[${provider.toUpperCase()} STREAM]: `);
      const stream = await model.stream(messages, { callbacks: [telemetry] });

      for await (const chunk of stream) {
        const text = typeof chunk.content === "string" ? chunk.content : "";
        process.stdout.write(text);
      }
      process.stdout.write("\n\n");
    } catch (err: any) {
      console.log(pc.red(`Failed on ${provider}: ${err.message}`));
    }
  }

  console.log("Telemetry Summary:", telemetry.getSummary());
}

if (process.argv[1]?.includes("unifiedChat")) {
  const sysPrompt = "You are an enterprise telecom assistant. Be concise and technical.";
  const query = "Explain why single-mode optical fiber has lower dispersion than multimode fiber.";
  compareUnifiedChat(query, sysPrompt).catch(console.error);
}

