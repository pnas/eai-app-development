import { z } from "zod";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";

export const TelecomIncidentSchema = z.object({
  incidentId: z.string().describe("Unique ticket identifier formatted as TICKET-XXXX"),
  severity: z.enum(["P1-CRITICAL", "P2-HIGH", "P3-MEDIUM", "P4-LOW"]).describe("Incident SLA priority"),
  affectedSubsystems: z.array(z.enum(["5G-RAN", "CORE-EPC", "IMS-VOICE", "FIBER-BACKHAUL", "BSS-BILLING"])),
  rootCauseHypothesis: z.string().describe("Probable root cause summary"),
  recommendedAction: z.string().describe("Immediate mitigation playbook action"),
  estimatedImpactSubscribers: z.number().int().nonnegative().describe("Estimated affected subscriber count"),
});

export type TelecomIncident = z.infer<typeof TelecomIncidentSchema>;

function hasKeyForProvider(provider: string): boolean {
  if (provider === "openai") return Boolean(process.env.OPENAI_API_KEY);
  if (provider === "anthropic") return Boolean(process.env.ANTHROPIC_API_KEY);
  if (provider === "gemini") return Boolean(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY);
  return false;
}

export async function extractIncidentTriage(
  reportText: string,
  provider: "openai" | "anthropic" | "gemini" | string = "openai"
): Promise<TelecomIncident> {
  if (!hasKeyForProvider(provider)) {
    console.log(pc.yellow(`[Notice] Missing API key for ${provider}. Providing mock structured extraction.`));
    return {
      incidentId: "TICKET-8812",
      severity: "P1-CRITICAL",
      affectedSubsystems: ["FIBER-BACKHAUL", "IMS-VOICE"],
      rootCauseHypothesis: "Primary fiber backhaul conduit severed during dredging work",
      recommendedAction: "Reroute traffic over microwave backup and deploy fiber splicing emergency crew",
      estimatedImpactSubscribers: 12000,
    };
  }

  const model = getChatModel(provider, { temperature: 0 });

  // Use LangChain's Zod-backed constrained structured output across OpenAI, Anthropic, or Gemini
  const structuredLlm = model.withStructuredOutput(TelecomIncidentSchema, {
    name: "TelecomIncidentTriage",
  });

  return (await structuredLlm.invoke(reportText)) as TelecomIncident;
}

export async function compareStructuredExtraction(
  reportText: string,
  providers: string[] = ["openai", "anthropic", "gemini"]
): Promise<Record<string, TelecomIncident | string>> {
  console.log(pc.yellow("\n=== Comparing Structured Extraction Across Frontier Models ==="));
  const results: Record<string, TelecomIncident | string> = {};

  for (const p of providers) {
    try {
      console.log(pc.cyan(`Invoking ${p.toUpperCase()} withStructuredOutput...`));
      const res = await extractIncidentTriage(reportText, p);
      results[p] = res;
      console.log(pc.green(`✔ ${p.toUpperCase()} extraction succeeded: Ticket ${res.incidentId}, Severity: ${res.severity}`));
    } catch (err: any) {
      console.log(pc.red(`✘ ${p.toUpperCase()} extraction error: ${err.message}`));
      results[p] = `ERROR: ${err.message}`;
    }
  }

  return results;
}

if (process.argv[1]?.includes("structuredOutput")) {
  const sampleReport = `
    URGENT OUTAGE REPORT: Incident TICKET-8812 reported at 09:14 UTC.
    Multiple cell towers in Hamburg port district lost connectivity.
    Primary fiber backhaul conduit severed during dredging work.
    Voice IMS calls degraded; estimated 12,000 active subscribers affected.
  `;

  console.log(pc.yellow("\n=== Module 2 (TypeScript): Structured Output with Zod Across Providers ===\n"));
  compareStructuredExtraction(sampleReport).catch(console.error);
}
