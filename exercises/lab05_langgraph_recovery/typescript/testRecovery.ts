import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";
import { ChatResult } from "@langchain/core/outputs";
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";
import { buildAgentGraph, resumeAgentWorkflow } from "./solution.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const testDbPath = path.join(__dirname, "test_lab05.db");

class DeterministicMockAgentModel extends BaseChatModel {
  _llmType(): string {
    return "deterministic_mock";
  }

  bindTools() {
    return this;
  }

  async _generate(messages: any[]): Promise<ChatResult> {
    const hasToolMsg = messages.some((m) => m instanceof ToolMessage || m._getType?.() === "tool");
    if (hasToolMsg) {
      const text = "I have confirmed your subscriber account is active with plan 5G-Max.";
      return {
        generations: [{ text, message: new AIMessage(text) }],
      };
    } else {
      const toolCall = {
        name: "query_subscriber",
        args: { accountId: "ACCT-99" },
        id: "call_mock_123",
      };
      return {
        generations: [
          {
            text: "",
            message: new AIMessage({
              content: "",
              tool_calls: [toolCall],
            }),
          },
        ],
      };
    }
  }
}

test("Lab 05: Agent executes tool loop and persists checkpoints to SQLite", async () => {
  if (fs.existsSync(testDbPath)) {
    try {
      fs.unlinkSync(testDbPath);
    } catch {}
  }

  const saver = SqliteSaver.fromConnString(testDbPath);
  const model = new DeterministicMockAgentModel({});
  const agent = buildAgentGraph(model, saver);

  const threadId = "test-session-ts-001";
  const config = { configurable: { thread_id: threadId } };

  const result = await agent.invoke(
    { messages: [new HumanMessage("Check my account ACCT-99")] },
    config
  );

  const messages = result.messages;
  assert.ok(messages.some((m: any) => m instanceof ToolMessage || m._getType?.() === "tool"));
  const lastMsg = messages.at(-1);
  assert.equal(lastMsg.content, "I have confirmed your subscriber account is active with plan 5G-Max.");

  // Check SQLite checkpoints table
  const row = saver.db.prepare("SELECT count(*) as cnt FROM checkpoints WHERE thread_id = ?").get(threadId) as { cnt: number };
  assert.ok(row.cnt >= 3, `Expected at least 3 checkpoints, got ${row.cnt}`);

  saver.db.close();
});

test("Lab 05: Agent recovers from crash via SQLite state and resumes cleanly", async () => {
  const threadId = "test-session-ts-crash";
  const config = { configurable: { thread_id: threadId } };

  // Phase 1: Run Turn 1 and kill agent
  const saver1 = SqliteSaver.fromConnString(testDbPath);
  const model = new DeterministicMockAgentModel({});
  let agent1: any = buildAgentGraph(model, saver1);

  await agent1.invoke(
    { messages: [new HumanMessage("First prompt")] },
    config
  );

  saver1.db.close();
  agent1 = null;

  // Phase 2: Boot new instance and rehydrate
  const saver2 = SqliteSaver.fromConnString(testDbPath);
  const agent2 = buildAgentGraph(model, saver2);

  const savedState = await agent2.getState(config);
  assert.ok(savedState);
  assert.ok(savedState.values.messages.length >= 3);

  // Phase 3: Resume
  const resumed = await resumeAgentWorkflow(agent2, threadId, "Thank you, goodbye.");
  assert.ok(resumed.messages.length > savedState.values.messages.length);

  saver2.db.close();
  if (fs.existsSync(testDbPath)) {
    try {
      fs.unlinkSync(testDbPath);
    } catch {}
  }
});

