import pc from "picocolors";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";

const STATIC_DOC = `
# TELEKOM COMPLIANCE STANDARDS: AUDITING & RETENTION RULES
Every transaction processed through the billing API must retain immutable audit logs for 7 years.
Audit trails must include caller identity, IP address, timestamp, HMAC signature, and response code.
In the event of an audit alert, the compliance officer must be notified via PagerDuty within 15 minutes.
`.concat("\nAll data pipelines must comply with GDPR Article 17 Right to Erasure.\n".repeat(450));

async function runBenchmark() {
  const client = getOpenAIClient();
  const model = "gpt-4o-mini";

  console.log(pc.bold("\n=== Prompt Cache Invalidation Benchmark (TypeScript) ===\n"));

  // 1. Anti-Pattern: Dynamic timestamp in prefix
  console.log(pc.red("1. Anti-Pattern: Dynamic Timestamp in System Prefix"));
  for (let i = 1; i <= 2; i++) {
    const dynamicPrompt = `Timestamp: ${new Date().toISOString()}\n\n${STATIC_DOC}`;
    const res = await client.chat.completions.create({
      model,
      messages: [
        { role: "system", content: dynamicPrompt },
        { role: "user", content: "What is the retention period?" },
      ],
      max_tokens: 15,
    });

    const usage: any = res.usage;
    const promptTok = usage?.prompt_tokens ?? 0;
    const cachedTok = usage?.prompt_tokens_details?.cached_tokens ?? 0;
    const hitPct = promptTok ? ((cachedTok / promptTok) * 100).toFixed(1) : "0.0";

    console.log(
      `  Run ${i}: Total Tok=${promptTok}, ` +
      pc.red(`Cached=${cachedTok} (${hitPct}% Hit)`)
    );
  }

  // 2. Best Practice: Invariant Static Prefix First
  console.log(pc.green("\n2. Best Practice: Invariant Static Prefix First"));
  const context = new Date().toISOString();
  for (let i = 1; i <= 2; i++) {
    const res = await client.chat.completions.create({
      model,
      messages: [
        { role: "system", content: `System Compliance Engine:\n\n${STATIC_DOC}` },
        { role: "user", content: `[Context: ${context}]\nWhat is the retention period?` },
      ],
      max_tokens: 15,
    });

    const usage: any = res.usage;
    const promptTok = usage?.prompt_tokens ?? 0;
    const cachedTok = usage?.prompt_tokens_details?.cached_tokens ?? 0;
    const hitPct = promptTok ? ((cachedTok / promptTok) * 100).toFixed(1) : "0.0";

    console.log(
      `  Run ${i}: Total Tok=${promptTok}, ` +
      pc.green(`Cached=${cachedTok} (${hitPct}% Hit)`)
    );
  }
}

runBenchmark().catch(console.error);

