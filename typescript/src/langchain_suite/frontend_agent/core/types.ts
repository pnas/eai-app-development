/**
 * Common types and SSE event contracts for the TypeScript Frontend Agent.
 */

export interface ChatMessageItem {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  prompt?: string;
  messages?: ChatMessageItem[];
  provider?: "mock" | "openai" | "anthropic" | "gemini";
  model?: string;
  threadId?: string;
}

export interface TokenEvent {
  event: "token";
  content: string;
}

export interface ToolStartEvent {
  event: "tool_start";
  tool: string;
  input: Record<string, unknown>;
}

export interface ToolEndEvent {
  event: "tool_end";
  tool: string;
  output: string;
}

export interface DoneEvent {
  event: "done";
  status: string;
}

export interface ErrorEvent {
  event: "error";
  error: string;
}

export type AgentStreamEvent =
  | TokenEvent
  | ToolStartEvent
  | ToolEndEvent
  | DoneEvent
  | ErrorEvent;

