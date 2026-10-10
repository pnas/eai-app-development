import { tool } from "@langchain/core/tools";
import { z } from "zod";
import pc from "picocolors";

const CUSTOMER_DB: Record<string, { name: string; plan: string; msisdn: string; status: string; balance: string }> = {
  "ACCT-1001": {
    name: "Acme Logistics GmbH",
    plan: "Enterprise 5G Ultra Unlimited",
    msisdn: "+491701234567",
    status: "ACTIVE",
    balance: "€240.00",
  },
  "ACCT-2002": {
    name: "Dr. Klaus Weber",
    plan: "MagentaMobil L 5G",
    msisdn: "+491519876543",
    status: "ACTIVE",
    balance: "€14.50",
  },
};

export const lookupTelecomAccount = tool(
  async ({ accountId }) => {
    const record = CUSTOMER_DB[accountId.trim().toUpperCase()];
    if (!record) {
      return `Error: Account ID '${accountId}' not found in registry.`;
    }
    return `Subscriber: ${record.name} | Status: ${record.status} | Plan: ${record.plan} | Phone: ${record.msisdn} | Balance: ${record.balance}`;
  },
  {
    name: "lookup_telecom_account",
    description: "Look up subscriber details, MSISDN phone number, active plan, and current balance.",
    schema: z.object({
      accountId: z.string().describe("Formatted account identifier, e.g. 'ACCT-1001'"),
    }),
  }
);

export const diagnoseNetworkCell = tool(
  async ({ msisdn }) => {
    console.log(pc.magenta(`⚡ Probing cell tower RF signal for ${msisdn}...`));
    return `Diagnostic Result for ${msisdn}: Attached Tower DE-FRA-088. 5G NR RSRP -104 dBm (Degraded), Packet Loss 8.2%, BFD Jitter 45ms. Alert: Tower sector 2 undergoing active maintenance.`;
  },
  {
    name: "diagnose_network_cell",
    description: "Run real-time radio line and cell tower diagnostics for a phone number.",
    schema: z.object({
      msisdn: z.string().describe("International phone number starting with +49..."),
    }),
  }
);

export const applyRetentionCredit = tool(
  async ({ accountId, amountEur, reason }) => {
    const key = accountId.trim().toUpperCase();
    if (!CUSTOMER_DB[key]) {
      return `Error: Cannot credit non-existent account '${accountId}'.`;
    }
    if (amountEur > 50.0) {
      return `Error: Credit amount €${amountEur.toFixed(2)} exceeds €50.00 supervisor limit.`;
    }
    return `SUCCESS: Credited €${amountEur.toFixed(2)} to account ${key}. Reason: '${reason}'. Token: TX-902144.`;
  },
  {
    name: "apply_retention_credit",
    description: "Apply goodwill financial compensation credit to a subscriber's account.",
    schema: z.object({
      accountId: z.string().describe("Formatted account ID, e.g. 'ACCT-1001'"),
      amountEur: z.number().describe("Credit amount in Euros (max 50.00)"),
      reason: z.string().describe("Business justification for credit approval"),
    }),
  }
);

export const agentTools = [lookupTelecomAccount, diagnoseNetworkCell, applyRetentionCredit];

