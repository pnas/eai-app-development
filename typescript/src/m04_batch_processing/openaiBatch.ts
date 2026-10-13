/**
 * Module 4: OpenAI Batch API Pipeline (TypeScript).
 *
 * Demonstrates:
 * 1. Formatting requests into .jsonl with custom_ids.
 * 2. Uploading the batch file via client.files.create({ file, purpose: "batch" }).
 * 3. Submitting the batch job with 24h completion window (50% cost discount).
 * 4. Polling with exponential backoff until completion.
 * 5. Downloading and correlating line-by-line responses.
 */

import pc from "picocolors";
import { toFile } from "openai";
import { getOpenAIClient } from "../m01_paradigms/clientFactory.js";

export function createSampleBatchPayload(): string {
  const prompts = [
    { custom_id: "task-001", text: "Classify sentiment: 'The migration was flawless and latency dropped 40%'" },
    { custom_id: "task-002", text: "Classify sentiment: 'Database connection timeouts caused an outage on Friday'" },
    { custom_id: "task-003", text: "Classify sentiment: 'The new pricing model is acceptable but documentation is sparse'" },
  ];

  return prompts
    .map((p) =>
      JSON.stringify({
        custom_id: p.custom_id,
        method: "POST",
        url: "/v1/chat/completions",
        body: {
          model: "gpt-4o-mini",
          messages: [
            { role: "system", content: "Respond with one word: POSITIVE, NEGATIVE, or NEUTRAL." },
            { role: "user", content: p.text },
          ],
          max_tokens: 10,
        },
      })
    )
    .join("\n");
}

export async function runOpenaiBatchWorkflow() {
  console.log(pc.bold("\n=== OpenAI Batch API Pipeline (TypeScript) ===\n"));

  let hasKey = Boolean(process.env.OPENAI_API_KEY);

  console.log(pc.cyan("1. Generating JSONL batch payload..."));
  const jsonlContent = createSampleBatchPayload();
  const lineCount = jsonlContent.split("\n").length;
  console.log(pc.white(`Generated ${lineCount} batch tasks.\n`));

  if (!hasKey) {
    console.log(pc.yellow("[SIMULATED RUN] No OPENAI_API_KEY found. Demonstrating simulated batch lifecycle..."));
    console.log(pc.green("✔ Mock File uploaded: file-batch-simulated-99482"));
    console.log(pc.green("✔ Mock Batch submitted! Batch ID: batch_sim_88310, Status: validating"));
    console.log(pc.cyan("  Polling status: in_progress (Completed: 1/3)"));
    console.log(pc.cyan("  Polling status: in_progress (Completed: 3/3)"));
    console.log(pc.green("✔ Mock Batch status: completed"));
    console.log("\nBatch Results Summary (Simulated):");
    console.log("task-001 -> POSITIVE");
    console.log("task-002 -> NEGATIVE");
    console.log("task-003 -> NEUTRAL\n");
    return;
  }

  try {
    const client = getOpenAIClient();

    console.log(pc.cyan("2. Uploading batch file to OpenAI Files API..."));
    const file = await toFile(Buffer.from(jsonlContent, "utf-8"), "batch_requests.jsonl", {
      type: "application/jsonl",
    });

    const uploadedFile = await client.files.create({
      file,
      purpose: "batch",
    });
    console.log(pc.green(`✔ File uploaded successfully! File ID: ${uploadedFile.id}\n`));

    console.log(pc.cyan("3. Creating batch job (50% cost discount)..."));
    const batchJob = await client.batches.create({
      input_file_id: uploadedFile.id,
      endpoint: "/v1/chat/completions",
      completion_window: "24h",
      metadata: { course: "advanced-ai-integration", environment: "training" },
    });
    console.log(pc.green(`✔ Batch job submitted! Batch ID: ${batchJob.id}, Status: ${batchJob.status}\n`));

    console.log(pc.cyan("4. Polling batch status (with backoff, max 30s demonstration)..."));
    let pollInterval = 3000;
    const maxWaitMs = 30000;
    const startTime = Date.now();
    let completedJob: any = null;

    while (Date.now() - startTime < maxWaitMs) {
      const status = await client.batches.retrieve(batchJob.id);
      const counts = status.request_counts;
      const completed = counts?.completed ?? 0;
      const total = counts?.total ?? 0;
      console.log(pc.yellow(`  Status: ${status.status} (Completed: ${completed}/${total})`));

      if (["completed", "failed", "expired", "cancelled"].includes(status.status)) {
        completedJob = status;
        break;
      }

      await new Promise((r) => setTimeout(r, pollInterval));
      pollInterval = Math.min(pollInterval * 1.5, 10000);
    }

    if (!completedJob || completedJob.status !== "completed") {
      console.log(pc.yellow(`\nBatch is still running asynchronously (ID: ${batchJob.id}). In production, batch runs asynchronously up to 24h.`));
      return;
    }

    console.log(pc.cyan("\n5. Downloading batch results..."));
    if (completedJob.output_file_id) {
      const fileResponse = await client.files.content(completedJob.output_file_id);
      const text = await fileResponse.text();
      console.log(pc.green("✔ Results downloaded successfully:"));
      console.log(text);
    }
  } catch (err: any) {
    console.log(pc.red(`OpenAI batch error: ${err.message}`));
  }
}

if (process.argv[1]?.includes("openaiBatch")) {
  runOpenaiBatchWorkflow().catch(console.error);
}
