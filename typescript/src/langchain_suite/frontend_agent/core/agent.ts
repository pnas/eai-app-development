/**
 * Core LangGraph Agent Factory and Lifecycle Event Streamer (TypeScript).
 *
 * Assembles cyclical tool-calling agents with persistence, and normalizes
 * LangGraph v2 execution events into unified frontend lifecycle messages:
 * `token`, `tool_start`, `tool_end`, `error`, `done`.
 */

import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import {
  AIMessage,
  BaseMessage,
  HumanMessage,
  SystemMessage,
} from "@langchain/core/messages";
import { StructuredToolInterface } from "@langchain/core/tools";
import { Annotation, MemorySaver, START, StateGraph } from "@langchain/langgraph";
import { ToolNode, toolsCondition } from "@langchain/langgraph/prebuilt";
import { BaseCheckpointSaver } from "@langchain/langgraph-checkpoint";

import { getChatModel } from "../../core/models.js";
import { globalToolRegistry } from "../tools/registry.js";
import { MockAgentChatModel } from "./mockModel.js";
import {
  AgentStreamEvent,
  ChatMessageItem,
} from "./types.js";

export const SYSTEM_PROMPT = `You are a helpful and polite AI assistant integrated into a dual-mode Web architecture demo.
You have access to tools:
- get_current_time: Check real-time date/time across different world timezones.
- get_random_quote: Fetch inspiring quotes categorized by technology, philosophy, science, or motivation.

Always use these tools whenever the user asks for time, date, quotes, or inspiration.
Be concise, clear, and informative.`;

export const AgentState = Annotation.Root({
  messages: Annotation<BaseMessage[]>({
    reducer: (x, y) => x.concat(y),
    default: () => [],
  }),
});

export interface CreateAgentOptions {
  provider?: "mock" | "openai" | "anthropic" | "gemini";
  model?: string;
  tools?: StructuredToolInterface[];
  checkpointer?: BaseCheckpointSaver;
}

/**
 * Builds and compiles a cyclical LangGraph tool-calling agent.
 */
export function createAgent(options: CreateAgentOptions = {}) {
  const {
    provider = "mock",
    model,
    tools = globalToolRegistry.getAll(),
    checkpointer,
  } = options;

  let chatModel: BaseChatModel;
  const provLower = provider.toLowerCase();

  if (provLower === "mock") {
    chatModel = new MockAgentChatModel();
  } else {
    chatModel = getChatModel(provLower as "openai" | "anthropic" | "gemini", {
      model,
      temperature: 0.0,
      streaming: true,
    });
  }

  const modelWithTools = (chatModel as any).bindTools
    ? (chatModel as any).bindTools(tools)
    : chatModel;

  async function agentNode(state: typeof AgentState.State) {
    let messages = state.messages;
    if (messages.length === 0 || !(messages[0] instanceof SystemMessage)) {
      messages = [new SystemMessage(SYSTEM_PROMPT), ...messages];
    }
    const response = await modelWithTools.invoke(messages);
    return { messages: [response] };
  }

  const toolNode = new ToolNode(tools);

  const workflow = new StateGraph(AgentState)
    .addNode("agent", agentNode)
    .addNode("tools", toolNode)
    .addEdge(START, "agent")
    .addConditionalEdges("agent", toolsCondition)
    .addEdge("tools", "agent");

  const saver = checkpointer ?? new MemorySaver();
  return workflow.compile({ checkpointer: saver });
}

/**
 * Helper to convert ChatMessageItem or raw prompts into LangChain BaseMessage instances.
 */
export function toBaseMessages(
  input: string | ChatMessageItem[] | BaseMessage[]
): BaseMessage[] {
  if (typeof input === "string") {
    return [new HumanMessage(input)];
  }

  return input.map((item) => {
    if (item instanceof BaseMessage || (item as any)._getType) {
      return item as BaseMessage;
    }
    const { role, content } = item as ChatMessageItem;
    if (role === "assistant") return new AIMessage(content);
    if (role === "system") return new SystemMessage(content);
    return new HumanMessage(content);
  });
}

/**
 * Yields normalized lifecycle events from the LangGraph agent execution.
 */
export async function* streamAgentLifecycle(
  agent: ReturnType<typeof createAgent>,
  messages: BaseMessage[],
  threadId: string = "default-session"
): AsyncGenerator<AgentStreamEvent> {
  const config = { configurable: { thread_id: threadId } };

  try {
    const eventStream = (agent as any).streamEvents(
      { messages },
      { ...config, version: "v2" }
    );

    for await (const event of eventStream) {
      const kind = event.event;

      // 1. Chat model streaming token chunks
      if (kind === "on_chat_model_stream") {
        const chunk = event.data?.chunk;
        if (chunk && chunk.content) {
          if (typeof chunk.content === "string" && chunk.content.length > 0) {
            yield { event: "token", content: chunk.content };
          } else if (Array.isArray(chunk.content)) {
            for (const part of chunk.content) {
              if (typeof part === "string" && part.length > 0) {
                yield { event: "token", content: part };
              } else if (typeof part === "object" && part && "text" in part && part.text) {
                yield { event: "token", content: String(part.text) };
              }
            }
          }
        }
      }

      // 2. Tool invocation initiated
      else if (kind === "on_tool_start") {
        const toolName = event.name ?? "unknown_tool";
        const toolInput = event.data?.input ?? {};
        yield { event: "tool_start", tool: toolName, input: toolInput };
      }

      // 3. Tool execution completed
      else if (kind === "on_tool_end") {
        const toolName = event.name ?? "unknown_tool";
        const rawOutput = event.data?.output;
        let toolOutput = "";
        if (typeof rawOutput === "string") {
          toolOutput = rawOutput;
        } else if (rawOutput && typeof rawOutput.content === "string") {
          toolOutput = rawOutput.content;
        } else {
          toolOutput = JSON.stringify(rawOutput ?? "");
        }
        yield { event: "tool_end", tool: toolName, output: toolOutput };
      }
    }

    // Final signal indicating stream completion
    yield { event: "done", status: "completed" };
  } catch (err: any) {
    yield { event: "error", error: err?.message ?? String(err) };
  }
}

