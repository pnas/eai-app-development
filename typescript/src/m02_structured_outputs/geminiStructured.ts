/**
 * Module 2: Google Gemini Structured Output (TypeScript).
 *
 * Demonstrates native grammar-constrained JSON decoding using Google GenAI SDK:
 * 1. Setting responseMimeType: "application/json"
 * 2. Supplying responseSchema conforming to the target schema
 * 3. Validation via Zod (SystemArchitectureSpecSchema)
 *
 * Official References:
 * - Google GenAI TypeScript SDK: https://github.com/googleapis/genai-js
 * - Gemini Structured Outputs: https://ai.google.dev/gemini-api/docs/structured-output
 */

import pc from "picocolors";
import { getGeminiClient } from "../m01_paradigms/clientFactory.js";
import { SystemArchitectureSpecSchema, type SystemArchitectureSpec } from "./schemas.js";

const ARCH_PROMPT = `
Perform an architectural assessment of our customer-facing payment gateway.
It currently consists of a monolithic Django app connected to a single un-replicated PostgreSQL
instance hosted in AWS us-east-1. We experience 250 requests/sec at peak, and daily downtime
during database backups. The team estimates running costs around $4,200/month.
`;

const geminiArchitectureSchema = {
  type: "OBJECT" as const,
  properties: {
    systemName: {
      type: "STRING" as const,
      description: "Official name of the architecture or service.",
    },
    estimatedMonthlyTcoUsd: {
      type: "NUMBER" as const,
      description: "Total cost of ownership estimation in USD.",
    },
    scalabilityRating1To10: {
      type: "INTEGER" as const,
      description: "Scale of 1-10.",
    },
    risks: {
      type: "ARRAY" as const,
      items: {
        type: "OBJECT" as const,
        properties: {
          componentName: { type: "STRING" as const },
          riskLevel: {
            type: "STRING" as const,
            enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
          },
          description: { type: "STRING" as const },
          mitigationStrategy: { type: "STRING" as const },
        },
        required: ["componentName", "riskLevel", "description", "mitigationStrategy"],
      },
    },
    recommendedPatterns: {
      type: "ARRAY" as const,
      items: { type: "STRING" as const },
    },
  },
  required: [
    "systemName",
    "estimatedMonthlyTcoUsd",
    "scalabilityRating1To10",
    "risks",
    "recommendedPatterns",
  ],
};

export async function extractWithGeminiSchema(): Promise<SystemArchitectureSpec> {
  const client = getGeminiClient();
  const primaryModel = "gemini-3.8-flash";
  const fallbackModel = "gemini-2.5-flash";

  console.log(pc.green(`Calling Google Gemini (${primaryModel}) with native responseSchema...`));
  let response;
  try {
    response = await client.models.generateContent({
      model: primaryModel,
      contents: ARCH_PROMPT,
      config: {
        responseMimeType: "application/json",
        responseSchema: geminiArchitectureSchema as any,
        temperature: 0.1,
      },
    });
  } catch (err: any) {
    console.log(pc.yellow(`Primary model ${primaryModel} failed (${err.message}), trying fallback ${fallbackModel}...`));
    response = await client.models.generateContent({
      model: fallbackModel,
      contents: ARCH_PROMPT,
      config: {
        responseMimeType: "application/json",
        responseSchema: geminiArchitectureSchema as any,
        temperature: 0.1,
      },
    });
  }

  const text = response.text;
  if (!text) {
    throw new Error("Empty response received from Gemini");
  }

  const rawJson = JSON.parse(text);
  const validatedSpec = SystemArchitectureSpecSchema.parse(rawJson);
  return validatedSpec;
}

export async function main() {
  try {
    const spec = await extractWithGeminiSchema();
    console.log(pc.green(`\n=== Google Gemini Extracted Architecture Spec ===`));
    console.log(pc.bold("System:"), spec.systemName);
    console.log(pc.bold("Scalability:"), `${spec.scalabilityRating1To10}/10`);
    console.log(pc.bold("Estimated Monthly Cost:"), `$${spec.estimatedMonthlyTcoUsd.toLocaleString()}`);
    console.log(pc.yellow(`\nIdentified Risks (${spec.risks.length}):`));
    spec.risks.forEach((r) => {
      console.log(`  - [${r.riskLevel}] ${r.componentName}: ${r.description}`);
    });
    console.log(pc.cyan(`\nRecommended Patterns: ${spec.recommendedPatterns.join(", ")}\n`));
  } catch (err: any) {
    console.log(pc.red(`Google Gemini structured output error: ${err.message}`));
  }
}

if (process.argv[1] && process.argv[1].endsWith("geminiStructured.ts")) {
  main().catch(console.error);
}
