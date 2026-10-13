/**
 * Module 2: Anthropic Native Document Citations (TypeScript).
 *
 * Demonstrates:
 * - Document content blocks with `citations: { enabled: true }`
 * - Parsing citation locations (char_location, page_location, content_block_location)
 * - Zero-token billing exemption for cited passages
 * - Incompatibility constraints (no prefills, no structured outputs)
 *
 * Reference:
 * - https://platform.claude.com/docs/en/build-with-claude/citations
 * - https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 */

import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";

const SLA_DOCUMENT = `
TELEKOM ENTERPRISE CLOUD SERVICE LEVEL AGREEMENT (SLA)
Document Version: 2026.4
Effective Date: January 1, 2026

1. SERVICE AVAILABILITY COMMITMENT
Telekom guarantees a Monthly Uptime Percentage of at least 99.99% for all Multi-Region
Enterprise Cloud Services during any monthly billing cycle. Service availability is measured
by automated health probes querying the /healthz endpoint every 10 seconds.

2. SERVICE CREDIT REBATE SCHEDULE
If Telekom fails to meet the Monthly Uptime Commitment, Customer is eligible to receive
Service Credits as follows:
- Monthly Uptime 99.0% to < 99.99%: 10% credit of monthly billing for the affected service.
- Monthly Uptime 95.0% to < 99.0%: 25% credit of monthly billing for the affected service.
- Monthly Uptime < 95.0%: 50% credit of monthly billing for the affected service.

3. EXCLUSIONS AND SCHEDULED MAINTENANCE
Maintenance windows are scheduled exclusively between Sunday 02:00 UTC and 04:00 UTC.
Outages resulting from customer misconfiguration, expired TLS certificates, or uncoordinated
load testing exceeding 10x baseline are strictly excluded from SLA credit calculations.
`;

async function queryDocumentWithCitations(question: string) {
  const client = getAnthropicClient();

  console.log(pc.magenta("Querying Claude 5.5 with grounded document citations..."));
  console.log(pc.cyan(`Question: ${question}\n`));

  // Note: Temperature and top_p MUST NOT be set on Claude 4.7+ / 5.x
  const response = await client.messages.create({
    model: "claude-sonnet-5-5",
    max_tokens: 1500,
    output_config: { effort: "medium" },
    messages: [
      {
        role: "user",
        content: [
          {
            type: "document",
            source: {
              type: "text",
              media_type: "text/plain",
              data: SLA_DOCUMENT,
            },
            title: "Telekom Enterprise SLA 2026",
            citations: { enabled: true },
          } as any,
          {
            type: "text",
            text: question,
          },
        ],
      },
    ],
  } as any);

  console.log(pc.green("=== Grounded Answer & Citation Trace ==="));

  let totalCitations = 0;
  for (const block of response.content) {
    if (block.type === "text") {
      console.log(block.text);

      const citations = (block as any).citations;
      if (Array.isArray(citations) && citations.length > 0) {
        console.log(pc.yellow("\n--- Citations Extracted ---"));
        for (const c of citations) {
          totalCitations++;
          console.log(
            pc.cyan(`[${c.type || "char_location"}]`) +
              ` Doc: "${c.document_title || "Telekom SLA"}" | Chars: [${c.start_char_index ?? "N/A"}:${c.end_char_index ?? "N/A"}]`
          );
          console.log(pc.gray(`Quote: "${c.cited_text}"\n`));
        }
      }
    }
  }

  console.log(pc.magenta("\n=== Usage & Cost Economics ==="));
  console.log(`Input Tokens: ${response.usage.input_tokens}`);
  console.log(`Output Tokens: ${response.usage.output_tokens}`);
  console.log(
    pc.green("Zero-Token Benefit: Quoted passages inside citations are 100% exempt from billable output tokens.")
  );
  console.log(pc.red("Rule: Citations CANNOT be combined with Structured Outputs or Prefills (HTTP 400).\n"));
}

async function main() {
  try {
    await queryDocumentWithCitations(
      "What is the guaranteed uptime commitment, and what credit rebate do I get if uptime falls below 95%?"
    );
  } catch (err: any) {
    console.log(pc.red(`Anthropic Citations error: ${err.message}`));
  }
}

main().catch(console.error);
