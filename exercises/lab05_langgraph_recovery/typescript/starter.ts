import { Annotation, StateGraph, START } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
import { BaseMessage, HumanMessage } from "@langchain/core/messages";
import { tool } from "@langchain/core/tools";
import { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";
import { z } from "zod";

// =============================================================================
// TASK 1: Define Typed State Schema with Append Reducer
// =============================================================================
// TODO: Implement Annotation.Root with reducer (x, y) => x.concat(y) so messages append.
export const ResilientAgentState = Annotation.Root({
  // Fix this placeholder:
  messages: Annotation<BaseMessage[]>(),
  executionStep: Annotation<number>(),
});

// Domain Tools (Provided)
export const querySubscriber = tool(
  async ({ accountId }) => {
    return `Subscriber ${accountId}: Status ACTIVE, Phone +491701234567, Plan 5G-Max`;
  },
  {
    name: "query_subscriber",
    description: "Lookup subscriber records by account ID.",
    schema: z.object({
      accountId: z.string().describe("Account ID e.g. ACCT-99"),
    }),
  }
);

export const issueRefund = tool(
  async ({ accountId, amountEur }) => {
    return `REFUND SUCCESS: €${amountEur.toFixed(2)} credited to ${accountId}. Ref: TX-${accountId}`;
  },
  {
    name: "issue_refund",
    description: "Issue goodwill refund credit to account.",
    schema: z.object({
      accountId: z.string(),
      amountEur: z.number(),
    }),
  }
);

export const LAB_TOOLS = [querySubscriber, issueRefund];

// =============================================================================
// TASK 2: Assemble StateGraph with Checkpointer
// =============================================================================
export function buildAgentGraph(model: any, checkpointer?: BaseCheckpointSaver) {
  // TODO:
  // 1. Bind LAB_TOOLS to model.
  // 2. Add 'agent' and 'tools' nodes.
  // 3. Connect START -> 'agent'.
  // 4. Add conditional edge from 'agent' via toolsCondition.
  // 5. Connect 'tools' -> 'agent'.
  // 6. Compile with checkpointer.
  return null as any;
}

// =============================================================================
// TASK 3: Resume Workflow Utility
// =============================================================================
export async function resumeAgentWorkflow(
  agent: any,
  threadId: string,
  followupMessage?: string
) {
  // TODO:
  // 1. Retrieve state using agent.getState(config).
  // 2. Throw Error if thread not found.
  // 3. Call agent.invoke() and return updated state.
  return null as any;
}

