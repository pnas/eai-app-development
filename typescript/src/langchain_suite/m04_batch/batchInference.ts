import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";

const TELECOM_QUERIES = [
  "Subscriber reports 4G fallback in central Berlin despite 5G SA subscription.",
  "BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.",
  "eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.",
  "Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.",
  "Roaming handshake timeout with partner network in Switzerland.",
];

async function runBatchInference(maxConcurrency = 3) {
  const model = getChatModel("openai", { temperature: 0 });
  const systemPrompt = "You are a network operations assistant. Provide a 1-sentence recommended action.";

  const inputs = TELECOM_QUERIES.map((q) => [
    new SystemMessage(systemPrompt),
    new HumanMessage(q),
  ]);

  console.log(pc.yellow(`\n=== Module 4 (TypeScript): Concurrent Batching (Concurrency=${maxConcurrency}) ===\n`));
  const startTime = performance.now();

  const results = await model.batch(inputs, {
    maxConcurrency,
  });

  const durationSec = ((performance.now() - startTime) / 1000).toFixed(2);
  console.log(pc.green(`✔ Successfully processed ${results.length} queries in ${durationSec}s:\n`));

  results.forEach((res, idx) => {
    console.log(pc.cyan(`[Query ${idx + 1}] ${TELECOM_QUERIES[idx]}`));
    console.log(pc.white(`Action: ${String(res.content).trim()}\n`));
  });
}

if (process.argv[1]?.includes("batchInference")) {
  runBatchInference(3).catch(console.error);
}

