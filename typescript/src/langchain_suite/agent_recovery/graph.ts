import { Annotation, StateGraph, START } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
import { BaseMessage, SystemMessage } from "@langchain/core/messages";
import { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";
import { getChatModel } from "../core/models.js";
import { agentTools } from "./tools.js";

const SYSTEM_PROMPT = `
You are an autonomous Tier-2 Technical Support Agent for a mobile telecom provider.
You have access to 3 tools:
1. lookup_telecom_account: Look up subscriber name, plan, phone number, and balance.
2. diagnose_network_cell: Check RF tower health and packet loss for a phone number.
3. apply_retention_credit: Apply up to €50 goodwill balance credit if an active outage degraded service.

Always check the account first to find the subscriber's phone number, run diagnostics,
and if degraded service is detected, apply goodwill credit and explain findings to the user.
`;

export const AgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: (x, y) => x.concat(y),
    default: () => [],
  }),
  agentStep: Annotation<number>({
    reducer: (x, y) => y ?? x,
    default: () => 0,
  }),
});

export function buildTelecomAgent(checkpointer?: BaseCheckpointSaver) {
  const model = (getChatModel("openai", { model: "gpt-4o-mini", temperature: 0 }) as any).bindTools(agentTools);

  async function agentNode(state: typeof AgentState.State) {
    let messages = state.messages;
    if (messages.length === 0 || !(messages[0] instanceof SystemMessage)) {
      messages = [new SystemMessage(SYSTEM_PROMPT), ...messages];
    }

    const response = await model.invoke(messages);
    return {
      messages: [response],
      agentStep: (state.agentStep ?? 0) + 1,
    };
  }

  const toolNode = new ToolNode(agentTools);

  const workflow = new StateGraph(AgentState)
    .addNode("agent", agentNode)
    .addNode("tools", toolNode)
    .addEdge(START, "agent")
    .addConditionalEdges("agent", toolsCondition)
    .addEdge("tools", "agent");

  return workflow.compile({ checkpointer });
}

