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

export async function extractIncidentTriage(reportText: string): Promise<TelecomIncident> {
  const model = getChatModel("openai", { temperature: 0 });

  // Use LangChain's Zod-backed constrained structured output
  const structuredLlm = model.withStructuredOutput(TelecomIncidentSchema, {
    name: "TelecomIncidentTriage",
  });

  return (await structuredLlm.invoke(reportText)) as TelecomIncident;
}

if (process.argv[1]?.includes("structuredOutput")) {
  const sampleReport = `
    URGENT OUTAGE REPORT: Incident TICKET-8812 reported at 09:14 UTC.
    Multiple cell towers in Hamburg port district lost connectivity.
    Primary fiber backhaul conduit severed during dredging work.
    Voice IMS calls degraded; estimated 12,000 active subscribers affected.
  `;

  console.log(pc.yellow("\n=== Module 2 (TypeScript): Structured Output with Zod ===\n"));
  extractIncidentTriage(sampleReport)
    .then((triage) => {
      console.log(pc.green("Structured Incident Extracted:"));
      console.dir(triage, { depth: null });
    })
    .catch(console.error);
}

