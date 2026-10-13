/**
 * Deterministic Mock Chat Model for offline testing and educational demonstrations.
 *
 * Allows running the full TypeScript Web UI + SSE streaming pipeline without requiring
 * active OpenAI, Anthropic, or Gemini API keys.
 */

import { CallbackManagerForLLMRun } from "@langchain/core/callbacks/manager";
import { BaseChatModel, BaseChatModelParams } from "@langchain/core/language_models/chat_models";
import {
  AIMessage,
  AIMessageChunk,
  BaseMessage,
  ToolMessage,
} from "@langchain/core/messages";
import { ChatGeneration, ChatGenerationChunk, ChatResult } from "@langchain/core/outputs";

export interface MockAgentChatModelParams extends BaseChatModelParams {
  modelName?: string;
}

export class MockAgentChatModel extends BaseChatModel {
  modelName: string;

  constructor(fields?: MockAgentChatModelParams) {
    super(fields ?? {});
    this.modelName = fields?.modelName ?? "mock-agent-v1";
  }

  _llmType(): string {
    return "mock-agent-chat-model";
  }

  bindTools(_tools: any[], _kwargs?: any): this {
    return this;
  }

  private determineAction(messages: BaseMessage[]): {
    toolCall: { name: string; args: Record<string, unknown>; id: string } | null;
    replyText: string;
  } {
    // 1. Check if the last message is a ToolMessage (tool already executed)
    if (messages.length > 0) {
      const last = messages[messages.length - 1];
      if (last instanceof ToolMessage || (last as any)._getType?.() === "tool" || (last as any).type === "tool") {
        return {
          toolCall: null,
          replyText: `I processed the tool output: ${String(last.content)}\n\nIs there anything else you'd like to check?`,
        };
      }
    }

    // 2. Find the latest user message
    let userText = "";
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      const type = (m as any)._getType?.() ?? (m as any).type;
      if (type === "human" || m.name === "user") {
        userText = String(m.content).toLowerCase();
        break;
      }
    }

    // 3. Check for time tool trigger
    if (/(time|clock|date|hour|now|timezone)/i.test(userText)) {
      let tz = "UTC";
      if (userText.includes("berlin") || userText.includes("germany")) tz = "Europe/Berlin";
      else if (userText.includes("new york") || userText.includes("ny")) tz = "America/New_York";
      else if (userText.includes("tokyo") || userText.includes("japan")) tz = "Asia/Tokyo";
      else if (userText.includes("athens") || userText.includes("greece")) tz = "Europe/Athens";
      else if (userText.includes("london") || userText.includes("uk")) tz = "Europe/London";

      return {
        toolCall: {
          name: "get_current_time",
          args: { timezone: tz },
          id: "mock_call_time_1",
        },
        replyText: "",
      };
    }

    // 4. Check for quote tool trigger
    if (/(quote|inspire|inspiration|wisdom|motto|saying)/i.test(userText)) {
      let category = "general";
      if (userText.includes("tech") || userText.includes("software") || userText.includes("code")) {
        category = "technology";
      } else if (userText.includes("philo") || userText.includes("life")) {
        category = "philosophy";
      } else if (userText.includes("motivat") || userText.includes("success")) {
        category = "motivation";
      } else if (userText.includes("sci")) {
        category = "science";
      }

      return {
        toolCall: {
          name: "get_random_quote",
          args: { category },
          id: "mock_call_quote_1",
        },
        replyText: "",
      };
    }

    // 5. Default conversational greeting
    return {
      toolCall: null,
      replyText:
        "Hello! I am your AI assistant equipped with real-time tools. " +
        "You can ask me for the current time in various cities (e.g., 'What time is it in Berlin?') " +
        "or ask for an inspiring quote (e.g., 'Give me a technology quote!').",
    };
  }

  async _generate(
    messages: BaseMessage[],
    _options: this["ParsedCallOptions"],
    _runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const { toolCall, replyText } = this.determineAction(messages);

    if (toolCall) {
      const message = new AIMessage({
        content: "",
        tool_calls: [
          {
            name: toolCall.name,
            args: toolCall.args,
            id: toolCall.id,
            type: "tool_call",
          },
        ],
      });
      return { generations: [{ text: "", message }] };
    }

    const message = new AIMessage({ content: replyText });
    return { generations: [{ text: replyText, message }] };
  }

  async *_streamResponseChunks(
    messages: BaseMessage[],
    _options: this["ParsedCallOptions"],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    const { toolCall, replyText } = this.determineAction(messages);

    if (toolCall) {
      const chunk = new AIMessageChunk({
        content: "",
        tool_call_chunks: [
          {
            name: toolCall.name,
            args: JSON.stringify(toolCall.args),
            id: toolCall.id,
            index: 0,
            type: "tool_call_chunk",
          },
        ],
      });
      yield new ChatGenerationChunk({ message: chunk, text: "" });
    } else {
      // Split words and whitespace to stream natural token chunks
      const tokens = replyText.match(/\S+|\s+/g) ?? [replyText];
      for (const token of tokens) {
        if (runManager) {
          await runManager.handleLLMNewToken(token);
        }
        const chunk = new AIMessageChunk({ content: token });
        yield new ChatGenerationChunk({ message: chunk, text: token });
      }
    }
  }
}

