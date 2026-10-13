/**
 * Lab 02 TypeScript Reference Solution: Prompt Cache Optimization & Audit.
 */

import crypto from "node:crypto";
import { ToolConfig } from "./starter.js";

export class OptimizedPromptBuilder {
  // Anthropic limits
  public static readonly MIN_ANTHROPIC_CACHE_TOKENS = 1024;
  public static readonly MIN_ANTHROPIC_HAIKU_CACHE_TOKENS = 2048;
  public static readonly MAX_ANTHROPIC_BREAKPOINTS = 4;

  // OpenAI limits
  public static readonly MIN_OPENAI_CACHE_TOKENS = 1024;

  // Google Gemini Enterprise Agent Platform context caching limits
  public static readonly MIN_GEMINI_2_CACHE_TOKENS = 2048;
  public static readonly MIN_GEMINI_3_CACHE_TOKENS = 4096;
  public static readonly MIN_GEMINI_3_IMPLICIT_PREVIEW_TOKENS = 6144;

  public static estimateTokens(text: string): number {
    return Math.floor(text.length / 4);
  }

  public static isAnthropicCacheEligible(
    tokenCount: number,
    model: string = "claude-3-7-sonnet-20250219"
  ): boolean {
    const m = model.toLowerCase();
    if (m.includes("haiku")) {
      return tokenCount >= this.MIN_ANTHROPIC_HAIKU_CACHE_TOKENS;
    }
    return tokenCount >= this.MIN_ANTHROPIC_CACHE_TOKENS;
  }

  public static isOpenAICacheEligible(
    tokenCount: number,
    _model: string = "gpt-4o"
  ): boolean {
    return tokenCount >= this.MIN_OPENAI_CACHE_TOKENS;
  }

  public static countAnthropicBreakpoints(payload: any): number {
    let count = 0;
    // Check top-level request automatic cache_control
    if (payload && typeof payload === "object" && payload.cache_control) {
      count++;
    }
    // Check system
    if (Array.isArray(payload.system)) {
      for (const block of payload.system) {
        if (block && typeof block === "object" && block.cache_control) {
          count++;
        }
      }
    }
    // Check tools
    if (Array.isArray(payload.tools)) {
      for (const tool of payload.tools) {
        if (tool && typeof tool === "object" && tool.cache_control) {
          count++;
        }
      }
    }
    // Check messages
    if (Array.isArray(payload.messages)) {
      for (const msg of payload.messages) {
        if (msg && typeof msg === "object") {
          if (Array.isArray(msg.content)) {
            for (const part of msg.content) {
              if (part && typeof part === "object" && part.cache_control) {
                count++;
              }
            }
          } else if (msg.cache_control) {
            count++;
          }
        }
      }
    }
    return count;
  }

  public static isGeminiCacheEligible(
    tokenCount: number,
    model: string = "gemini-2.5-flash",
    implicitPreview: boolean = false
  ): boolean {
    const m = model.toLowerCase();
    if (m.includes("gemini-3") || m.includes("gemini-3.")) {
      if (
        implicitPreview ||
        m.includes("3.0-flash-preview") ||
        m.includes("3.1-pro-preview") ||
        m.includes("3.7-flash") ||
        m.includes("3.8-flash")
      ) {
        return tokenCount >= this.MIN_GEMINI_3_IMPLICIT_PREVIEW_TOKENS;
      }
      return tokenCount >= this.MIN_GEMINI_3_CACHE_TOKENS;
    }
    return tokenCount >= this.MIN_GEMINI_2_CACHE_TOKENS;
  }

  public static buildOptimizedPayload(
    documentationKb: string,
    toolsConfig: ToolConfig,
    userTicket: string,
    timestamp?: string,
    ttl: string = "5m"
  ): any {
    // 1. Deterministic sorted serialization
    const sortedKeys = Object.keys(toolsConfig).sort();
    const sortedObj: Record<string, any> = {};
    for (const key of sortedKeys) {
      sortedObj[key] = toolsConfig[key];
    }
    const toolsJson = JSON.stringify(sortedObj);

    // 2. Build static prefix
    let staticPrefix =
      "### SYSTEM POLICIES & KNOWLEDGE BASE ###\n" +
      documentationKb.trim() +
      "\n\n### AVAILABLE TOOL SPECS ###\n" +
      toolsJson;

    // 3. Meet 1024 token threshold
    const currentTokens = this.estimateTokens(staticPrefix);
    if (currentTokens < this.MIN_ANTHROPIC_CACHE_TOKENS) {
      const neededTokens = this.MIN_ANTHROPIC_CACHE_TOKENS - currentTokens + 50;
      const padding =
        "\n### EXTENDED CONTEXT GUIDELINES ###\n" +
        "Ensure strict compliance with internal quality and security guidelines. ".repeat(
          Math.ceil(neededTokens / 10)
        );
      staticPrefix += padding;
    }

    // 4. Dynamic content placed in user message
    const timeStr = timestamp || "2026-10-10T00:00:00Z";
    const dynamicUserContent = `[Current Timestamp: ${timeStr}]\nUser Ticket: ${userTicket}`;

    const cacheControlObj: Record<string, any> = { type: "ephemeral" };
    if (ttl && ttl !== "5m") {
      cacheControlObj.ttl = ttl;
    }

    return {
      model: "claude-3-7-sonnet-20250219",
      system: [
        {
          type: "text",
          text: staticPrefix,
          cache_control: cacheControlObj,
        },
      ],
      messages: [
        {
          role: "user",
          content: dynamicUserContent,
        },
      ],
    };
  }

  public static diagnoseCacheMiss(
    baseline: Record<string, any>,
    current: Record<string, any>,
    provider: string = "auto"
  ): { type: "cache_hit" | "cache_miss"; reason: string | null; cache_missed_input_tokens?: number } {
    /**
     * Diagnose why two consecutive requests caused a cache miss or hit.
     * Supports both OpenAI and Anthropic Cache Diagnostics reason taxonomies.
     */
    const isAnthropic =
      provider === "anthropic" ||
      (provider === "auto" &&
        (String(baseline.model || "").toLowerCase().startsWith("claude") ||
          String(current.model || "").toLowerCase().startsWith("claude")) &&
        baseline.prompt_cache_key === undefined &&
        baseline.reasoning_effort === undefined);

    // 1. Model changed (common to both)
    if (baseline.model !== current.model) {
      const res: any = { type: "cache_miss", reason: "model_changed" };
      if (isAnthropic) {
        res.cache_missed_input_tokens = this.estimateTokens(
          JSON.stringify(current.system || "") + JSON.stringify(current.messages || "")
        );
      }
      return res;
    }

    // 2. Anthropic previous_message_id check
    if (isAnthropic && "previous_message_id" in current) {
      const baselineId = baseline.id || baseline.response_id;
      if (current.previous_message_id !== baselineId) {
        return {
          type: "cache_miss",
          reason: "previous_message_not_found",
          cache_missed_input_tokens: this.estimateTokens(
            JSON.stringify(current.system || "") + JSON.stringify(current.messages || "")
          ),
        };
      }
    }

    // 3. OpenAI routing and configuration
    if (!isAnthropic) {
      if (baseline.prompt_cache_key !== current.prompt_cache_key) {
        return { type: "cache_miss", reason: "prompt_cache_key_changed" };
      }

      if (baseline.reasoning_effort !== current.reasoning_effort) {
        return { type: "cache_miss", reason: "reasoning_effort_changed" };
      }
    }

    // 4. Tools changed (common to both)
    const bTools = baseline.tools ? JSON.stringify(baseline.tools) : null;
    const cTools = current.tools ? JSON.stringify(current.tools) : null;
    if (bTools !== cTools) {
      const res: any = { type: "cache_miss", reason: "tools_changed" };
      if (isAnthropic) {
        res.cache_missed_input_tokens = this.estimateTokens(JSON.stringify(current.tools || ""));
      }
      return res;
    }

    // 5. System prompt changed
    const bHash = computePrefixHash(baseline.system || []);
    const cHash = computePrefixHash(current.system || []);
    if (bHash !== cHash) {
      if (isAnthropic) {
        return {
          type: "cache_miss",
          reason: "system_changed",
          cache_missed_input_tokens: this.estimateTokens(JSON.stringify(current.system || "")),
        };
      }
      return { type: "cache_miss", reason: "input_changed" };
    }

    // 6. Messages changed (Anthropic fine-grained audit)
    if (isAnthropic) {
      const bMsgs = JSON.stringify(baseline.messages || []);
      const cMsgs = JSON.stringify(current.messages || []);
      const bPrefix = bMsgs.length > 2 ? bMsgs.slice(0, -1) : "[";
      if (!cMsgs.startsWith(bPrefix)) {
        return {
          type: "cache_miss",
          reason: "messages_changed",
          cache_missed_input_tokens: this.estimateTokens(JSON.stringify(current.messages || "")),
        };
      }
    }

    return { type: "cache_hit", reason: null };
  }
}

export function computePrefixHash(systemBlocks: any): string {
  if (typeof systemBlocks === "string") {
    return crypto.createHash("sha256").update(systemBlocks, "utf8").digest("hex");
  }
  let concatenated = "";
  if (Array.isArray(systemBlocks)) {
    for (const block of systemBlocks) {
      if (typeof block === "string") {
        concatenated += block;
      } else if (block && typeof block === "object") {
        concatenated += block.text || "";
        if (block.cache_control) break;
      }
    }
  }
  return crypto.createHash("sha256").update(concatenated, "utf8").digest("hex");
}

