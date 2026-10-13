/**
 * Extensible Tool Registry for TypeScript Frontend Agent Showcase.
 *
 * Facilitates plug-and-play tool registration, discovery, and schema inspection.
 */

import { StructuredTool } from "@langchain/core/tools";
import { zodToJsonSchema } from "zod-to-json-schema";
import { getCurrentTime, getRandomQuote } from "./defaultTools.js";

export interface ToolMetadata {
  name: string;
  description: string;
  schema: Record<string, unknown>;
}

export class ToolRegistry {
  private tools: Map<string, StructuredTool> = new Map();

  constructor(initialTools?: StructuredTool[]) {
    const defaults = initialTools ?? [getCurrentTime, getRandomQuote];
    for (const t of defaults) {
      this.register(t);
    }
  }

  public register(toolInstance: StructuredTool): void {
    this.tools.set(toolInstance.name, toolInstance);
  }

  public get(name: string): StructuredTool | undefined {
    return this.tools.get(name);
  }

  public getAll(): StructuredTool[] {
    return Array.from(this.tools.values());
  }

  public getMetadata(): ToolMetadata[] {
    return Array.from(this.tools.values()).map((toolInstance) => {
      let schemaObj: Record<string, unknown> = {};
      if (toolInstance.schema) {
        try {
          schemaObj = zodToJsonSchema(toolInstance.schema as any, "ToolSchema") as Record<string, unknown>;
        } catch {
          schemaObj = {};
        }
      }
      return {
        name: toolInstance.name,
        description: toolInstance.description,
        schema: schemaObj,
      };
    });
  }

  public getSchemas(): ToolMetadata[] {
    return this.getMetadata();
  }
}

export const globalToolRegistry = new ToolRegistry();
