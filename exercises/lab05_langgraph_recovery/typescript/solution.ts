import { Annotation, StateGraph, START } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
import { BaseMessage, HumanMessage } from "@langchain/core/messages";
import { tool } from "@langchain/core/tools";
import { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";
import { z } from "zod";

// 1. Define Typed State Schema with Append Reducer
export const ResilientAgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: (x, y) => x.concat(y),
    default: () => [],
  }),
  executionStep: Annotation<number>({
    reducer: (x, y) => y ?? x,
    default: () => 0,
  }),
});

// 2. Domain Tools
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

// 3. Assemble StateGraph with Checkpointer
export function buildAgentGraph(model: any, checkpointer?: BaseCheckpointSaver) {
  const boundModel = typeof model.bindTools === "function" ? model.bindTools(LAB_TOOLS) : model;

  async function agentNode(state: typeof ResilientAgentState.State) {
    const response = await boundModel.invoke(state.messages);
    return {
      messages: [response],
      executionStep: (state.executionStep ?? 0) + 1,
    };
  }

  const toolNode = new ToolNode(LAB_TOOLS);

  const workflow = new StateGraph(ResilientAgentState)
    .addNode("agent", agentNode)
    .addNode("tools", toolNode)
    .addEdge(START, "agent")
    .addConditionalEdges("agent", toolsCondition)
    .addEdge("tools", "agent");

  return workflow.compile({ checkpointer });
}

// 4. Resume Workflow Utility
export async function resumeAgentWorkflow(
  agent: any,
  threadId: string,
  followupMessage?: string
) {
  const config = { configurable: { thread_id: threadId } };
  const state = await agent.getState(config);

  if (!state || !state.values || !state.values.messages) {
    throw new Error(`No checkpoint found for thread_id: '${threadId}'`);
  }

  const input = followupMessage
    ? { messages: [new HumanMessage(followupMessage)] }
    : null;

  return await agent.invoke(input, config);
}

