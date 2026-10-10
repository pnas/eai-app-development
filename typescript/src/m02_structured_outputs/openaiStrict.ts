import pc from "picocolors";
import { zodResponseFormat } from "openai/helpers/zod";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";
import { SystemArchitectureSpecSchema, type SystemArchitectureSpec } from "./schemas.js";

const ARCH_PROMPT = `
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
`;

async function extractWithOpenAIStrict(): Promise<SystemArchitectureSpec> {
  const client = getOpenAIClient();

  console.log(pc.cyan("Sending request to OpenAI with zodResponseFormat strict grammar..."));
  const completion = await client.beta.chat.completions.parse({
    model: "gpt-4o-2024-08-06",
    messages: [
      { role: "system", content: "You are a Principal Cloud Systems Architect." },
      { role: "user", content: ARCH_PROMPT },
    ],
    response_format: zodResponseFormat(SystemArchitectureSpecSchema, "systemArchitectureSpec"),
  });

  const message = completion.choices[0]?.message;
  if (message?.refusal) {
    throw new Error(`Model refused: ${message.refusal}`);
  }

  const parsed = message?.parsed;
  if (!parsed) {
    throw new Error("Failed to parse structured output");
  }

  return parsed;
}

async function main() {
  try {
    const spec = await extractWithOpenAIStrict();
    console.log(pc.green(`\n=== Extracted System Architecture Spec ===`));
    console.log(pc.bold("System:"), spec.systemName);
    console.log(pc.bold("Scalability:"), `${spec.scalabilityRating1To10}/10`);
    console.log(pc.bold("Estimated Monthly Cost:"), `$${spec.estimatedMonthlyTcoUsd.toLocaleString()}`);
    console.log(pc.yellow(`\nIdentified Risks (${spec.risks.length}):`));
    spec.risks.forEach((r) => {
      console.log(`  - [${r.riskLevel}] ${r.componentName}: ${r.description}`);
    });
    console.log(pc.cyan(`\nRecommended Patterns: ${spec.recommendedPatterns.join(", ")}\n`));
  } catch (err: any) {
    console.log(pc.red(`OpenAI strict parsing error: ${err.message}`));
  }
}

main().catch(console.error);

