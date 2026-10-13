/**
 * Unified LangChain Multi-Paradigm CLI (TypeScript).
 *
 * Demonstrates all 6 core GenAI architectural paradigms through LangChain abstractions:
 * 1. Unified Chat Models & Normalized Content Blocks (OpenAI, Anthropic, Gemini)
 * 2. Grammar-Constrained Structured Outputs with Zod
 * 3. Prompt Caching & Ephemeral Breakpoint Cost Optimization
 * 4. High-Throughput Concurrent Batch Processing with Concurrency Windows
 * 5. Resilience & Declarative Multi-Provider Fallback Cascades
 * 6. Enterprise Gateways (OpenRouter / LiteLLM) & Dynamic Cost Routing
 *
 * Supports both interactive terminal menu and flag-driven execution.
 * Supports live provider calls and offline simulated mock mode.
 */

import readline from "node:readline";
import pc from "picocolors";
import { compareUnifiedChat } from "./m01_paradigms/unifiedChat.js";
import { extractIncidentTriage, compareStructuredExtraction, TelecomIncidentSchema, type TelecomIncident } from "./m02_structured/structuredOutput.js";
import { runPromptCacheDemo } from "./m03_caching/promptCache.js";
import { runBatchInference } from "./m04_batch/batchInference.js";
import { demonstrateFallbackCascade } from "./m05_resilience/fallbackCascade.js";
import { demonstrateLangChainRateLimiting } from "./m05_resilience/rateLimitedChain.js";
import { routeAndExecute } from "./m06_gateways/costRouter.js";
import { runGatewayOrchestrationDemo } from "./m06_gateways/gatewayOrchestrator.js";

export async function runParadigm1(provider = "all", customQuery?: string) {
  console.log(pc.cyan(pc.bold("\n=== Paradigm 1: Unified Chat Models, Streaming & Telemetry ===")));
  console.log("LangChain normalizes vendor payloads into SystemMessage / HumanMessage / AIMessage\nand exposes a uniform .stream() iterator with callback telemetry.\n");

  const query = customQuery || "Explain in 2 sentences why fiber optic lines have lower attenuation than copper coaxial cable.";
  const sysPrompt = "You are an enterprise telecom assistant. Be concise and technical.";

  const hasKeys = Boolean(process.env.OPENAI_API_KEY || process.env.ANTHROPIC_API_KEY || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY);

  if (provider === "mock" || !hasKeys) {
    console.log(pc.yellow("Executing in SIMULATED MOCK MODE (no external API keys required):\n"));
    console.log(pc.bold("Provider        Model Abstraction   Tokens (In/Out)   Status"));
    console.log(pc.cyan("OPENAI          ") + "gpt-4.1-mini        28 / 18           " + pc.green("SUCCESS"));
    console.log(pc.yellow("ANTHROPIC       ") + "claude-haiku-5-5    28 / 17           " + pc.green("SUCCESS"));
    console.log(pc.magenta("GEMINI          ") + "gemini-3.8-flash    28 / 21           " + pc.green("SUCCESS"));
    console.log("\nTelemetry Summary: { invocations: 3, totalTokens: 140, totalCostUsd: '$0.000042' }\n");
    return;
  }

  await compareUnifiedChat(query, sysPrompt);
}

export async function runParadigm2(provider = "openai") {
  console.log(pc.green(pc.bold("\n=== Paradigm 2: Grammar-Constrained Structured Output with Zod ===")));
  console.log("Leverages .withStructuredOutput() across OpenAI, Anthropic, and Gemini.\n");

  const sampleReport = `
    URGENT OUTAGE REPORT: Incident TICKET-9942 reported at 14:22 UTC.
    Multiple eNodeB base stations in Frankfurt South cluster lost synchronization.
    Fiber backhaul rings experiencing 45% packet drop after third-party roadwork severed secondary dark fiber conduit.
    Voice IMS calls dropping; estimated 18,500 active mobile subscribers experiencing service degradation.
  `;

  if (provider === "mock") {
    console.log(pc.yellow("Mock mode selected. Showing validated Zod incident instance:"));
    const mockTriage: TelecomIncident = {
      incidentId: "TICKET-9942",
      severity: "P1-CRITICAL",
      affectedSubsystems: ["5G-RAN", "FIBER-BACKHAUL", "IMS-VOICE"],
      rootCauseHypothesis: "Third-party roadwork excavation severed secondary dark fiber conduit causing sync loss.",
      recommendedAction: "Reroute traffic to tertiary microwave link and dispatch fiber splicing emergency crew.",
      estimatedImpactSubscribers: 18500,
    };
    console.dir(mockTriage, { depth: null });
    return;
  }

  if (provider === "all") {
    await compareStructuredExtraction(sampleReport);
    return;
  }

  const triage = await extractIncidentTriage(sampleReport, provider);
  console.log(pc.green(`Successfully extracted structured incident (${provider}):`));
  console.dir(triage, { depth: null });
}

export async function runParadigm3(provider = "anthropic") {
  console.log(pc.yellow(pc.bold("\n=== Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics ===")));
  console.log("Injects cache_control: { type: 'ephemeral' } in SystemMessage content blocks.\nSubsequent requests reusing identical prefixes receive ~90% cost discount.\n");

  if (provider === "mock" || !process.env.ANTHROPIC_API_KEY) {
    console.log(pc.yellow("ANTHROPIC_API_KEY not set or mock mode selected. Displaying telemetry comparison:\n"));
    console.log(pc.bold("Turn     State              Input Tokens   Cache Creation   Cache Read   Cost Rate"));
    console.log("------------------------------------------------------------------------------------");
    console.log("Turn 1   Cache Miss (Cold)  1,248          1,248            0            100% standard");
    console.log("Turn 2   Cache Hit (Warm)   1,254          0                1,248        " + pc.blue("10% rate (90% discount!)") + "\n");
    return;
  }

  await runPromptCacheDemo();
}

export async function runParadigm4(provider = "all", concurrency = 3) {
  console.log(pc.magenta(pc.bold(`\n=== Paradigm 4: Concurrent Batch Inference (Concurrency Window = ${concurrency}) ===`)));
  console.log("Uses model.batch() with maxConcurrency across OpenAI, Anthropic, and Gemini.\n");

  if (provider === "mock") {
    console.log(pc.yellow("Simulating concurrent batch execution across 5 telecom queries:\n"));
    const mockResults = [
      { q: "Customer reports 4G fallback in central Berlin despite 5G SA subscription.", a: "Trigger PCRF QoS profile refresh and verify 5G provisioning flag." },
      { q: "BSS billing cycle failed for subscriber ID SUB-4401 due to currency mismatch.", a: "Initiate foreign exchange conversion adapter and retry invoice generation." },
      { q: "eNodeB antenna tilt misconfiguration suspected on sector 3, tower DE-BER-102.", a: "Dispatch remote electrical tilt (RET) adjustment via OSS telemetry." },
      { q: "Optical line terminal (OLT) reports loss of signal (LOS) on PON port 4.", a: "Dispatch field technician to inspect splitter cabinet 14-B." },
      { q: "Roaming handshake timeout with partner network in Switzerland.", a: "Verify Diameter routing agent (DRA) reachability and S9 interface timers." },
    ];
    mockResults.forEach((r, idx) => {
      console.log(pc.cyan(`[Query ${idx + 1}] ${r.q}`));
      console.log(pc.green(`Action: ${r.a}\n`));
    });
    return;
  }

  await runBatchInference(provider, concurrency);
}

export async function runParadigm5(simulateFailure = true) {
  console.log(pc.red(pc.bold("\n=== Paradigm 5: Resilience, Fallback Cascades & Token Rate Limiting ===")));
  console.log("Declarative failover via primary.withFallbacks([secondary, tertiary]).\nPre-call token bucket rate limiting (WSO2 pattern) with automatic failover.\n");
  await demonstrateFallbackCascade(simulateFailure);
  await demonstrateLangChainRateLimiting();
}

export async function runParadigm6(simulate = false) {
  console.log(pc.blue(pc.bold("\n=== Paradigm 6: Enterprise Gateways & Dynamic Cost-Based Routing ===")));
  console.log("Routes requests dynamically based on query complexity and interfaces with proxy gateways.\n");

  const queries = [
    "What is the acronym APN in mobile networking?",
    "Design a multi-region active-active BSS billing architecture handling 50k transactions/sec with zero split-brain.",
    "List the 3 primary bands used in European 5G NR.",
    "Provide an in-depth root cause analysis for optical polarization mode dispersion on 400G transponders.",
  ];

  console.log(pc.bold("Dynamic Model Routing & Unit Economics:"));
  for (const q of queries) {
    const res = await routeAndExecute(q, simulate);
    console.log(
      pc.cyan(`[${res.tier}] `) +
      pc.yellow(`Model: ${res.model} `) +
      pc.magenta(`Tokens: ${res.tokens} `) +
      pc.green(`Cost: ${res.costUsd} `) +
      pc.white(`Query: ${res.query}`)
    );
  }

  console.log(pc.cyan("\n--- Gateway Orchestration (OpenRouter / LiteLLM) ---"));
  await runGatewayOrchestrationDemo(simulate);
}

export async function runAll(provider = "auto") {
  console.log(pc.bold(pc.yellow("===============================================================================")));
  console.log(pc.bold(pc.yellow("     RUNNING COMPLETE 6-PARADIGM SUITE VIA LANGCHAIN ABSTRACTIONS (TS)        ")));
  console.log(pc.bold(pc.yellow("===============================================================================\n")));

  await runParadigm1(provider);
  console.log("\n" + "=".repeat(75) + "\n");
  await runParadigm2(provider);
  console.log("\n" + "=".repeat(75) + "\n");
  await runParadigm3(provider);
  console.log("\n" + "=".repeat(75) + "\n");
  await runParadigm4(provider);
  console.log("\n" + "=".repeat(75) + "\n");
  await runParadigm5(true);
  console.log("\n" + "=".repeat(75) + "\n");
  await runParadigm6(provider === "mock");
  console.log(pc.bold(pc.green("\n[OK] All 6 TypeScript paradigms executed successfully!\n")));
}

function askQuestion(rl: readline.Interface, query: string): Promise<string> {
  return new Promise((resolve) => rl.question(query, resolve));
}

export async function interactiveMenu() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  while (true) {
    console.log(pc.cyan("\n+============================================================================+"));
    console.log(pc.cyan("|          LangChain Multi-Paradigm Integration Suite CLI (TypeScript)       |"));
    console.log(pc.cyan("+============================================================================+"));
    console.log("  " + pc.yellow("1") + " - Paradigm 1: Unified Chat, Streaming & Telemetry (OpenAI, Anthropic, Gemini)");
    console.log("  " + pc.yellow("2") + " - Paradigm 2: Grammar-Constrained Structured Output (Zod)");
    console.log("  " + pc.yellow("3") + " - Paradigm 3: Prompt Caching & Ephemeral Breakpoint Economics");
    console.log("  " + pc.yellow("4") + " - Paradigm 4: Concurrent Batch Processing & Rate-Limit Windows");
    console.log("  " + pc.yellow("5") + " - Paradigm 5: Resilience & Multi-Provider Fallback Cascades");
    console.log("  " + pc.yellow("6") + " - Paradigm 6: Enterprise Gateways & Cost-Based Routing");
    console.log("  " + pc.yellow("A") + " - Run ALL 6 Paradigms in Sequence");
    console.log("  " + pc.yellow("Q") + " - Exit\n");

    const answer = (await askQuestion(rl, "Select an option [A]: ")).trim() || "A";

    if (answer.toLowerCase() === "q") {
      console.log(pc.green("Goodbye!"));
      rl.close();
      break;
    } else if (answer.toLowerCase() === "a") {
      await runAll("auto");
    } else if (answer === "1") {
      await runParadigm1("auto");
    } else if (answer === "2") {
      await runParadigm2("auto");
    } else if (answer === "3") {
      await runParadigm3("auto");
    } else if (answer === "4") {
      await runParadigm4("auto");
    } else if (answer === "5") {
      await runParadigm5(true);
    } else if (answer === "6") {
      await runParadigm6();
    }

    await askQuestion(rl, "\nPress Enter to return to the menu...");
  }
}

export async function main() {
  const args = process.argv.slice(2);

  let paradigmArg: string | undefined;
  let providerArg = "auto";
  let isInteractive = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-p" || args[i] === "--paradigm") {
      paradigmArg = args[++i];
    } else if (args[i] === "--provider") {
      providerArg = args[++i] || "auto";
    } else if (args[i] === "-i" || args[i] === "--interactive") {
      isInteractive = true;
    } else if (args[i] === "-h" || args[i] === "--help") {
      console.log(`
Usage: tsx src/langchain_suite/cli.ts [options]

Options:
  -p, --paradigm <1-6|all>   Execute specific paradigm or all
  --provider <mock|auto>     Target provider or mock mode (default: auto)
  -i, --interactive          Launch interactive terminal menu
  -h, --help                 Show help message
      `);
    } else if (["1", "2", "3", "4", "5", "6", "all"].includes(args[i].toLowerCase())) {
      paradigmArg = args[i].toLowerCase();
    } else if (["mock", "openai", "anthropic", "gemini", "auto"].includes(args[i].toLowerCase())) {
      providerArg = args[i].toLowerCase();
    }
  }

  if (args.length === 0 || isInteractive || !paradigmArg) {
    await interactiveMenu();
    return;
  }

  if (paradigmArg === "all") {
    await runAll(providerArg);
  } else if (paradigmArg === "1") {
    await runParadigm1(providerArg);
  } else if (paradigmArg === "2") {
    await runParadigm2(providerArg);
  } else if (paradigmArg === "3") {
    await runParadigm3(providerArg);
  } else if (paradigmArg === "4") {
    await runParadigm4(providerArg);
  } else if (paradigmArg === "5") {
    await runParadigm5(true);
  } else if (paradigmArg === "6") {
    await runParadigm6();
  } else {
    console.log(pc.red(`Unknown paradigm: ${paradigmArg}. Use 1-6 or 'all'.`));
  }
}

if (process.argv[1] && process.argv[1].endsWith("cli.ts")) {
  main().catch(console.error);
}
