import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import pc from "picocolors";
import { getChatModel } from "../core/models.js";

export const TELECOM_QUERIES = [
  "Subscriber reports 4G fallback in central Berlin despite 5G SA subscription.",
  "BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.",
  "eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.",
  "Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.",
  "Roaming handshake timeout with partner network in Switzerland.",
];

export interface ProviderBatchBenchmark {
  provider: string;
  model: string;
  queryCount: number;
  durationSec: number;
  throughput: number;
  status: "SUCCESS" | "SKIPPED" | "FAILED";
  error?: string;
}

function hasKeyForProvider(provider: string): boolean {
  if (provider === "openai") return Boolean(process.env.OPENAI_API_KEY);
  if (provider === "anthropic") return Boolean(process.env.ANTHROPIC_API_KEY);
  if (provider === "gemini") return Boolean(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY);
  return false;
}

function getProviderModelName(provider: string): string {
  if (provider === "openai") return process.env.OPENAI_MODEL ?? "gpt-4.1-mini";
  if (provider === "anthropic") return process.env.ANTHROPIC_MODEL ?? "claude-haiku-5-5";
  if (provider === "gemini") return process.env.GEMINI_MODEL ?? "gemini-3.8-flash";
  return provider;
}

export async function runBatchInference(
  providersOrConcurrency: string[] | string | number = "all",
  concurrency = 3
): Promise<ProviderBatchBenchmark[]> {
  let targetProviders: string[];
  let maxConcurrency = concurrency;

  if (typeof providersOrConcurrency === "number") {
    maxConcurrency = providersOrConcurrency;
    targetProviders = ["openai", "anthropic", "gemini"];
  } else if (providersOrConcurrency === "all") {
    targetProviders = ["openai", "anthropic", "gemini"];
  } else if (Array.isArray(providersOrConcurrency)) {
    targetProviders = providersOrConcurrency;
  } else {
    targetProviders = [providersOrConcurrency];
  }

  const systemPrompt = "You are a network operations assistant. Provide a 1-sentence recommended action.";
  const inputs = TELECOM_QUERIES.map((q) => [
    new SystemMessage(systemPrompt),
    new HumanMessage(q),
  ]);

  console.log(pc.yellow(`\n=== Module 4 (TypeScript): Multi-Provider Concurrent Batching ===`));
  console.log(pc.cyan(`Target Providers: [${targetProviders.join(", ")}] | Max Concurrency: ${maxConcurrency}\n`));

  const benchmarks: ProviderBatchBenchmark[] = [];

  for (const provider of targetProviders) {
    const modelName = getProviderModelName(provider);
    console.log(pc.bold(`\n--- Running Batch Inference on Provider: ${pc.magenta(provider.toUpperCase())} (${modelName}) ---`));

    if (!hasKeyForProvider(provider)) {
      console.log(pc.yellow(`[SKIPPED] Missing API credentials for ${provider}. Continuing without error.`));
      benchmarks.push({
        provider,
        model: modelName,
        queryCount: inputs.length,
        durationSec: 0,
        throughput: 0,
        status: "SKIPPED",
        error: "Missing API credentials in environment",
      });
      continue;
    }

    try {
      const model = getChatModel(provider, { temperature: 0 });
      const startTime = performance.now();

      const results = await model.batch(inputs, {
        maxConcurrency,
      });

      const elapsedMs = performance.now() - startTime;
      const durationSec = Number((elapsedMs / 1000).toFixed(2));
      const throughput = Number((results.length / (durationSec || 0.001)).toFixed(2));

      console.log(pc.green(`✔ ${provider.toUpperCase()}: Processed ${results.length} queries in ${durationSec}s (${throughput} q/s):`));

      results.forEach((res, idx) => {
        const text = typeof res.content === "string" ? res.content : JSON.stringify(res.content);
        console.log(pc.cyan(`  [Query ${idx + 1}] ${TELECOM_QUERIES[idx]}`));
        console.log(pc.white(`  Action: ${text.trim()}\n`));
      });

      benchmarks.push({
        provider,
        model: modelName,
        queryCount: results.length,
        durationSec,
        throughput,
        status: "SUCCESS",
      });
    } catch (err: any) {
      console.log(pc.red(`✘ ${provider.toUpperCase()} batch failed: ${err.message}`));
      benchmarks.push({
        provider,
        model: modelName,
        queryCount: inputs.length,
        durationSec: 0,
        throughput: 0,
        status: "FAILED",
        error: err.message,
      });
    }
  }

  // Summary Table
  console.log(pc.bold("\n=== Batch Inference Multi-Provider Performance Summary ==="));
  console.log(
    "Provider".padEnd(12) +
    "Model".padEnd(20) +
    "Queries".padEnd(10) +
    "Duration".padEnd(12) +
    "Throughput".padEnd(15) +
    "Status"
  );
  console.log("-".repeat(78));

  for (const b of benchmarks) {
    const durStr = b.status === "SUCCESS" ? `${b.durationSec}s` : "N/A";
    const tpStr = b.status === "SUCCESS" ? `${b.throughput} q/s` : "N/A";
    const statusStr = b.status === "SUCCESS" ? pc.green(b.status) : (b.status === "SKIPPED" ? pc.yellow(b.status) : pc.red(b.status));
    console.log(
      b.provider.padEnd(12) +
      b.model.padEnd(20) +
      String(b.queryCount).padEnd(10) +
      durStr.padEnd(12) +
      tpStr.padEnd(15) +
      statusStr
    );
  }
  console.log("-".repeat(78) + "\n");

  return benchmarks;
}

if (process.argv[1]?.includes("batchInference")) {
  runBatchInference("all", 3).catch(console.error);
}
