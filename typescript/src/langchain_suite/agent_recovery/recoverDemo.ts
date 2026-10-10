import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { HumanMessage } from "@langchain/core/messages";
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";
import pc from "picocolors";
import { buildTelecomAgent } from "./graph.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dbPath = path.join(__dirname, "telecom_checkpoints.db");

async function runRecoveryDemo() {
  console.log(pc.yellow("\n=== LangGraph TypeScript: SQLite State Persistence & Crash Recovery ===\n"));

  // Ensure clean test environment
  if (fs.existsSync(dbPath)) {
    try {
      fs.unlinkSync(dbPath);
    } catch {}
  }

  const threadId = "subscriber-incident-9021-ts";
  const config = { configurable: { thread_id: threadId } };

  console.log(pc.cyan(`1. Initializing SQLite Checkpointer at: ${path.basename(dbPath)}`));
  const saver = SqliteSaver.fromConnString(dbPath);
  let agent = buildTelecomAgent(saver);

  console.log(pc.cyan("\n2. Executing Initial Customer Turn..."));
  const initialPrompt = "Hello, my account ID is ACCT-1001. My mobile data is crawling and dropping calls. Can you check?";
  console.log(pc.white(`User: ${initialPrompt}\n`));

  const turn1Result = await agent.invoke(
    { messages: [new HumanMessage(initialPrompt)] },
    config
  );

  console.log(
    pc.green(`✔ Turn 1 completed. Messages in checkpoint: ${turn1Result.messages.length}`)
  );
  const lastAiMsg = turn1Result.messages.at(-1);
  console.log(`Agent: ${String(lastAiMsg?.content).slice(0, 160)}...\n`);

  // Close connection / kill instance to simulate worker crash
  saver.db.close();
  // @ts-ignore
  agent = null;
  console.log(pc.red("💥 PROCESS CRASH SIMULATION: Memory wiped, SQLite connection closed, agent killed.\n"));

  // =========================================================================
  // RECOVERY PHASE: New process instance boots up and connects to SQLite
  // =========================================================================
  console.log(pc.cyan("3. Spawning New Worker Process & Rehydrating State from SQLite..."));
  const recoveredSaver = SqliteSaver.fromConnString(dbPath);
  const recoveredAgent = buildTelecomAgent(recoveredSaver);

  const savedState = await recoveredAgent.getState(config);
  console.log(pc.yellow(`Rehydrated Thread: ${threadId}`));
  console.log(`Rehydrated Messages count: ${savedState.values.messages.length}`);
  console.log(`Next pending action node: ${JSON.stringify(savedState.next)}`);

  console.log(pc.cyan("\n4. Resuming Unfinished Process with Follow-up Action..."));
  const followupPrompt = "Thank you for the diagnosis. Could you please apply the retention credit now?";
  console.log(pc.white(`User: ${followupPrompt}\n`));

  const finalResult = await recoveredAgent.invoke(
    { messages: [new HumanMessage(followupPrompt)] },
    config
  );

  console.log(pc.green("✔ Successfully Resumed & Completed Workflow from SQLite Checkpoint:"));
  console.log(`Total messages in thread: ${finalResult.messages.length}`);
  console.log(pc.white(`\nFinal Response:\n${String(finalResult.messages.at(-1)?.content)}\n`));

  recoveredSaver.db.close();
  console.log(pc.green("✔ Demonstration Complete: Zero state lost across process destruction."));
}

if (process.argv[1]?.includes("recoverDemo")) {
  runRecoveryDemo().catch(console.error);
}

