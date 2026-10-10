import pc from "picocolors";
import { zodResponseFormat } from "openai/helpers/zod";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";
import { SystemArchitectureSpecSchema, type SystemArchitectureSpec } from "./schemas.js";

async function repairPayload(
  brokenJson: string,
  errorMessage: string,
  maxAttempts: number = 2
): Promise<SystemArchitectureSpec> {
  const client = getOpenAIClient();
  let currentPayload = brokenJson;
  let currentError = errorMessage;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(pc.yellow(`Attempt ${attempt}: Executing self-repair loop...`));

    const repairPrompt = `
The following JSON payload failed schema parsing:
---
${currentPayload}
---
The validation / syntax error was:
${currentError}

Fix all syntax errors, close unclosed strings or arrays, and return ONLY a valid JSON object.
`;

    const completion = await client.beta.chat.completions.parse({
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: "You are an automated JSON schema repair engine." },
        { role: "user", content: repairPrompt },
      ],
      response_format: zodResponseFormat(SystemArchitectureSpecSchema, "repairedSpec"),
    });

    const parsed = completion.choices[0]?.message?.parsed;
    if (parsed) {
      console.log(pc.green("Successfully repaired and validated schema!"));
      return parsed;
    }
  }

  throw new Error(`Self-repair failed after ${maxAttempts} attempts`);
}

async function main() {
  const brokenTruncatedJson = `{
    "systemName": "Legacy Core Banking Gateway",
    "estimatedMonthlyTcoUsd": 14000,
    "scalabilityRating1To10": 2,
    "risks": [
      {
        "componentName": "MQ Connector",
        "riskLevel": "CRITICAL",
        "description": "Single point of failure without failover",
        "mitigationStrategy": "Deploy Kafka cluster"
      }
    ],
    "recommendedPatterns": ["Circuit Breaker", "Read
  `;

  console.log(pc.red("\nSimulating broken/truncated JSON payload:"));
  console.log(pc.gray(brokenTruncatedJson));

  try {
    JSON.parse(brokenTruncatedJson);
  } catch (err: any) {
    console.log(pc.red(`\nDetected Parse Error: ${err.message}`));
    try {
      const repaired = await repairPayload(brokenTruncatedJson, err.message);
      console.log(pc.bold("\nRepaired System:"), repaired.systemName);
      console.log(pc.bold("Risks identified:"), repaired.risks.length);
      console.log(pc.bold("Patterns:"), repaired.recommendedPatterns.join(", "));
    } catch (repairErr: any) {
      console.log(pc.red(`Repair failed: ${repairErr.message}`));
    }
  }
}

main().catch(console.error);

