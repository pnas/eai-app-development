import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";
import { SystemArchitectureSpecSchema, type SystemArchitectureSpec } from "./schemas.js";

const ARCH_PROMPT = `
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
`;

async function extractWithAnthropicTool(): Promise<SystemArchitectureSpec> {
  const client = getAnthropicClient();
  const toolName = "record_architecture_spec";

  // Define input schema matching SystemArchitectureSpec
  const inputSchema = {
    type: "object" as const,
    properties: {
      systemName: { type: "string" },
      estimatedMonthlyTcoUsd: { type: "number" },
      scalabilityRating1To10: { type: "integer", minimum: 1, maximum: 10 },
      risks: {
        type: "array",
        items: {
          type: "object",
          properties: {
            componentName: { type: "string" },
            riskLevel: { type: "string", enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
            description: { type: "string" },
            mitigationStrategy: { type: "string" },
          },
          required: ["componentName", "riskLevel", "description", "mitigationStrategy"],
        },
      },
      recommendedPatterns: {
        type: "array",
        items: { type: "string" },
      },
    },
    required: ["systemName", "estimatedMonthlyTcoUsd", "scalabilityRating1To10", "risks", "recommendedPatterns"],
  };

  console.log(pc.magenta("Calling Anthropic Claude with forced tool schema..."));
  const response = await client.messages.create({
    model: "claude-3-5-sonnet-20241022",
    max_tokens: 2048,
    tools: [
      {
        name: toolName,
        description: "Emit formal architectural review specification.",
        input_schema: inputSchema,
      },
    ],
    tool_choice: { type: "tool", name: toolName },
    messages: [
      {
        role: "user",
        content: `Analyze this architecture and emit the specification:\n${ARCH_PROMPT}`,
      },
    ],
  });

  const toolUse = response.content.find((b) => b.type === "tool_use") as any;
  if (!toolUse) {
    throw new Error("Model failed to invoke forced tool");
  }

  // Validate the tool payload using Zod for 100% type safety
  const validated = SystemArchitectureSpecSchema.parse(toolUse.input);
  return validated;
}

async function main() {
  try {
    const spec = await extractWithAnthropicTool();
    console.log(pc.green(`\n=== Anthropic Structured Output Spec ===`));
    console.log(pc.bold("System:"), spec.systemName);
    console.log(pc.bold("Scalability:"), `${spec.scalabilityRating1To10}/10`);
    console.log(pc.bold("Estimated Monthly Cost:"), `$${spec.estimatedMonthlyTcoUsd.toLocaleString()}`);
    console.log(pc.yellow(`\nIdentified Risks (${spec.risks.length}):`));
    spec.risks.forEach((r) => {
      console.log(`  - [${r.riskLevel}] ${r.componentName}: ${r.description}`);
    });
    console.log(pc.cyan(`\nRecommended Patterns: ${spec.recommendedPatterns.join(", ")}\n`));
  } catch (err: any) {
    console.log(pc.red(`Anthropic structured error: ${err.message}`));
  }
}

main().catch(console.error);

