/**
 * Lab 02 TypeScript Reference Solution: Prompt Cache Optimization & Audit.
 */

import crypto from "node:crypto";
import { ToolConfig } from "./starter.js";

export class OptimizedPromptBuilder {
  public static readonly MIN_ANTHROPIC_CACHE_TOKENS = 1024;

  public static estimateTokens(text: string): number {
    return Math.floor(text.length / 4);
  }

  public static buildOptimizedPayload(
    documentationKb: string,
    toolsConfig: ToolConfig,
    userTicket: string,
    timestamp?: string
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

    return {
      model: "claude-3-7-sonnet-20250219",
      system: [
        {
          type: "text",
          text: staticPrefix,
          cache_control: { type: "ephemeral" },
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
}

export function computePrefixHash(systemBlocks: any[]): string {
  let concatenated = "";
  for (const block of systemBlocks) {
    concatenated += block.text || "";
    if (block.cache_control) break;
  }
  return crypto.createHash("sha256").update(concatenated, "utf8").digest("hex");
}

