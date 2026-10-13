/**
 * Module 2: Anthropic Structured Output Paradigms (TypeScript).
 *
 * Demonstrates schema enforcement on Anthropic Claude 5.5:
 * 1. Strict tool calling with `strict: true` and `additionalProperties: false`.
 * 2. Wire-level `output_config: { format: { type: "json_schema", schema: ... } }`.
 *
 * Reference:
 * - https://platform.claude.com/docs/en/build-with-claude/structured-outputs
 * - https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 */

import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";
import { SystemArchitectureSpecSchema, type SystemArchitectureSpec } from "./schemas.js";

const ARCH_PROMPT = `
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
`;

const ARCH_SCHEMA = {
  type: "object" as const,
  properties: {
    systemName: { type: "string" },
    estimatedMonthlyTcoUsd: { type: "number" },
    scalabilityRating1To10: { type: "integer", description: "Scalability rating between 1 and 10." },
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
        additionalProperties: false,
      },
    },
    recommendedPatterns: {
      type: "array",
      items: { type: "string" },
    },
  },
  required: ["systemName", "estimatedMonthlyTcoUsd", "scalabilityRating1To10", "risks", "recommendedPatterns"],
  additionalProperties: false,
};

/**
 * Extract structured data natively using Claude 5.5 wire-level JSON schema.
 * Matches Python client.messages.parse(output_format=...)
 */
async function extractWithAnthropicNativeParse(): Promise<SystemArchitectureSpec> {
  const client = getAnthropicClient();
  const model = "claude-sonnet-5-5";

  console.log(pc.magenta(`Calling Anthropic Claude (${model}) with native output_config JSON schema...`));
  // Note: Temperature/top_p MUST NOT be set on Claude 4.7+ / 5.x models.
  const response = await client.messages.create({
    model,
    max_tokens: 2048,
    output_config: {
      effort: "medium",
      format: {
        type: "json_schema",
        schema: ARCH_SCHEMA,
      },
    } as any,
    messages: [
      {
        role: "user",
        content: `Analyze this architecture and emit the specification:\n${ARCH_PROMPT}`,
      },
    ],
  } as any);

  const textBlock = response.content.find((b) => b.type === "text") as any;
  if (!textBlock || !textBlock.text) {
    throw new Error("Model failed to emit text content");
  }

  const rawJson = JSON.parse(textBlock.text);
  return SystemArchitectureSpecSchema.parse(rawJson);
}

/**
 * Extract structured data using strict tool calling (alternative schema enforcement).
 */
async function extractWithAnthropicStrictTool(): Promise<SystemArchitectureSpec> {
  const client = getAnthropicClient();
  const toolName = "record_architecture_spec";
  const model = "claude-sonnet-5-5";

  console.log(pc.magenta(`Calling Anthropic Claude (${model}) with strict tool schema...`));
  const response = await client.messages.create({
    model,
    max_tokens: 2048,
    output_config: { effort: "medium" } as any,
    tools: [
      {
        name: toolName,
        description: "Emit formal architectural review specification.",
        input_schema: ARCH_SCHEMA,
        strict: true,
      } as any,
    ],
    tool_choice: { type: "auto" },
    messages: [
      {
        role: "user",
        content: `Analyze this architecture and invoke the ${toolName} tool with the specification:\n${ARCH_PROMPT}`,
      },
    ],
  } as any);

  const toolUse = response.content.find((b) => b.type === "tool_use") as any;
  if (!toolUse) {
    throw new Error("Model failed to invoke tool");
  }

  return SystemArchitectureSpecSchema.parse(toolUse.input);
}

async function main() {
  try {
    const spec = await extractWithAnthropicNativeParse();
    console.log(pc.green(`\n=== Anthropic Native Structured Output Spec (claude-sonnet-5-5) ===`));
    console.log(pc.bold("System:"), spec.systemName);
    console.log(pc.bold("Scalability:"), `${spec.scalabilityRating1To10}/10`);
    console.log(pc.bold("Estimated Monthly Cost:"), `$${spec.estimatedMonthlyTcoUsd.toLocaleString()}`);
    console.log(pc.yellow(`\nIdentified Risks (${spec.risks.length}):`));
    spec.risks.forEach((r) => {
      console.log(`  - [${r.riskLevel}] ${r.componentName}: ${r.description}`);
    });
    console.log(pc.cyan(`\nRecommended Patterns: ${spec.recommendedPatterns.join(", ")}\n`));
  } catch (err: any) {
    console.log(pc.yellow(`Native parse error: ${err.message}. Trying strict tool calling...`));
    try {
      const spec = await extractWithAnthropicStrictTool();
      console.log(pc.green(`\n=== Anthropic Strict Tool Output Spec (claude-sonnet-5-5) ===`));
      console.log(pc.bold("System:"), spec.systemName);
      console.log(pc.bold("Scalability:"), `${spec.scalabilityRating1To10}/10`);
      console.log(pc.bold("Estimated Monthly Cost:"), `$${spec.estimatedMonthlyTcoUsd.toLocaleString()}`);
      console.log(pc.yellow(`\nIdentified Risks (${spec.risks.length}):`));
      spec.risks.forEach((r) => {
        console.log(`  - [${r.riskLevel}] ${r.componentName}: ${r.description}`);
      });
      console.log(pc.cyan(`\nRecommended Patterns: ${spec.recommendedPatterns.join(", ")}\n`));
    } catch (innerErr: any) {
      console.log(pc.red(`Anthropic structured error: ${innerErr.message}`));
    }
  }
}

main().catch(console.error);
