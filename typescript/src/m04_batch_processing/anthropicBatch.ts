/**
 * Module 4: Anthropic Message Batches API (TypeScript).
 *
 * Demonstrates submitting asynchronous batch requests to Anthropic Claude
 * with custom IDs and inspecting batch processing state.
 * Batches receive 50% pricing discount on modern Claude models (e.g. claude-haiku-5-5).
 *
 * Reference:
 * - https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 */

import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";

export async function runAnthropicBatchDemo() {
  console.log(pc.bold("\n=== Anthropic Message Batches API (TypeScript) ===\n"));

  const hasKey = Boolean(process.env.ANTHROPIC_API_KEY);
  const model = "claude-haiku-5-5";

  console.log(pc.magenta("1. Preparing Anthropic Message Batch requests..."));
  const requests = [
    {
      custom_id: "review-101",
      params: {
        model,
        max_tokens: 100,
        messages: [
          { role: "user" as const, content: "Generate a 1-sentence code review tip for TypeScript generics." },
        ],
      },
    },
    {
      custom_id: "review-102",
      params: {
        model,
        max_tokens: 100,
        messages: [
          { role: "user" as const, content: "Generate a 1-sentence code review tip for database transactions." },
        ],
      },
    },
  ];
  console.log(pc.white(`Prepared ${requests.length} batch requests.\n`));

  if (!hasKey) {
    console.log(pc.yellow("[SIMULATED RUN] No ANTHROPIC_API_KEY found. Demonstrating simulated batch lifecycle..."));
    console.log(pc.green("✔ Mock Message Batch created! Batch ID: msgbatch_sim_44129, Status: in_progress"));
    console.log(pc.magenta("Anthropic Batch Status:"));
    console.log("  Batch ID:          msgbatch_sim_44129");
    console.log("  Status:            in_progress");
    console.log("  Processing Counts: Processing: 2, Succeeded: 0, Errored: 0");
    console.log(`  Created At:        ${new Date().toISOString()}`);
    console.log(`  Expires At:        ${new Date(Date.now() + 86400000).toISOString()}`);
    console.log(pc.gray("\nIn production, poll until processing_status === 'ended', then fetch results.\n"));
    return;
  }

  try {
    const client = getAnthropicClient();
    console.log(pc.magenta("2. Creating Message Batch (50% Cost Discount)..."));

    let messageBatch: any;
    try {
      messageBatch = await client.messages.batches.create({ requests: requests as any });
    } catch {
      // Fallback model if key does not yet have 5.5 batch enabled
      for (const r of requests) {
        r.params.model = "claude-3-5-haiku-20241022";
      }
      messageBatch = await client.messages.batches.create({ requests: requests as any });
    }

    console.log(pc.green(`✔ Batch submitted! Batch ID: ${messageBatch.id}, Status: ${messageBatch.processing_status}\n`));

    console.log(pc.magenta("3. Inspecting batch status..."));
    const batchStatus = await client.messages.batches.retrieve(messageBatch.id);
    const counts = batchStatus.request_counts;

    console.log(pc.bold("Anthropic Batch Status:"));
    console.log(`  Batch ID:          ${batchStatus.id}`);
    console.log(`  Status:            ${batchStatus.processing_status}`);
    console.log(`  Processing Counts: Processing: ${counts.processing}, Succeeded: ${counts.succeeded}, Errored: ${counts.errored}`);
    console.log(`  Created At:        ${batchStatus.created_at}`);
    console.log(`  Expires At:        ${batchStatus.expires_at}`);
    console.log(pc.gray("\nIn production, poll until processing_status === 'ended', then iterate through client.messages.batches.results(batch_id)."));
  } catch (err: any) {
    console.log(pc.red(`Anthropic batch error: ${err.message}`));
  }
}

if (process.argv[1]?.includes("anthropicBatch")) {
  runAnthropicBatchDemo().catch(console.error);
}
