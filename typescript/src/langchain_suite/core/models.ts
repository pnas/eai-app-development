import { loadWorkspaceEnv } from "./env.js";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatOpenAI } from "@langchain/openai";
import { ChatAnthropic } from "@langchain/anthropic";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";

loadWorkspaceEnv();

/**
 * Core Model Factory for LangChain & LangGraph Integrations (TypeScript).
 *
 * Up-to-date Frontier Model Support (OpenAI GPT-4.1 / GPT-6, Anthropic Claude 5.5 / 4.5, Gemini 3.8 / 3.1).
 * Supports both legacy/transitional classes and modern frontier flagships per docs/api_comparison_matrix.md.
 */

export const DEFAULT_MODELS: Record<string, string> = {
  openai: "gpt-4.1-mini",
  anthropic: "claude-haiku-5-5",
  gemini: "gemini-3.8-flash",
};

export const PRIMARY_MODELS: Record<string, Record<string, string[]>> = {
  openai: {
    flagship_reasoning: ["gpt-6-astra", "gpt-6.1-sol"],
    fast_reasoning: ["gpt-6-luna"],
    high_throughput: ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
    legacy: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4"],
  },
  anthropic: {
    flagship: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
    specialized: ["claude-opus-5", "claude-fable-5-1", "claude-mythos-5-1"],
    v4_5_class: ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
    legacy: ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"],
  },
  gemini: {
    flagship: ["gemini-3.8-flash"],
    high_throughput: ["gemini-3.5-flash-lite"],
    frontier: ["gemini-3.1-pro-preview"],
    live: ["gemini-3.8-live", "gemini-3.8-live-extended-thinking"],
    legacy: ["gemini-2.5-pro", "gemini-2.0-flash"],
  },
};

/**
 * Detects if an OpenAI model is a dedicated reasoning model (gpt-6*, o1*, o3*, o4*).
 * Reasoning models reject standard temperature=0.0 and require fixed/omitted temperature.
 */
export function isReasoningModel(modelName: string): boolean {
  const m = modelName.toLowerCase().trim();
  return (
    ["gpt-6", "o1", "o3", "o4"].some((prefix) => m.startsWith(prefix)) ||
    m.includes("-reasoning")
  );
}

/**
 * Detects if an Anthropic model prohibits sampling parameters (temperature, top_p, top_k).
 * Per docs/api_comparison_matrix.md:
 * - Claude 4.7+ and Claude 5.x return HTTP 400 if temperature/top_p/top_k are supplied.
 * - Claude 4.5 class (opus-4-5, sonnet-4-5, haiku-4-5) and 3.x support temperature.
 */
export function isSamplingRestrictedAnthropic(modelName: string): boolean {
  const m = modelName.toLowerCase().trim();
  // Explicitly allow Claude 3.x and Claude 4.5 class
  if (m.includes("claude-3") || m.includes("4-5") || m.includes("4.5")) {
    return false;
  }
  if (/claude-(opus|sonnet|haiku|fable|mythos)?-?5[-.]/.test(m)) {
    return true;
  }
  return ["-5-5", "-5.5", "-5-1", "-5.1", "-4-7", "-4.7", "opus-5", "sonnet-5", "haiku-5"].some((p) =>
    m.includes(p)
  );
}

export interface ChatModelOptions {
  model?: string;
  temperature?: number;
  streaming?: boolean;
  [key: string]: any;
}

export function getChatModel(
  provider: "openai" | "anthropic" | "gemini" | string = "openai",
  options: ChatModelOptions = {}
): BaseChatModel {
  const { model, temperature = 0.0, streaming = true, ...extra } = options;

  switch (provider.toLowerCase()) {
    case "openai":
    case "open_ai": {
      const apiKey = process.env.OPENAI_API_KEY;
      if (!apiKey) throw new Error("OPENAI_API_KEY is not defined.");
      const modelName = model ?? DEFAULT_MODELS.openai;

      const openAiConfig: any = {
        model: modelName,
        streaming,
        apiKey,
        ...extra,
      };

      // Reasoning models (gpt-6*, o1*, o3*) do not accept temperature
      if (!isReasoningModel(modelName)) {
        openAiConfig.temperature = temperature;
      }

      return new ChatOpenAI(openAiConfig);
    }

    case "anthropic":
    case "claude": {
      const apiKey = process.env.ANTHROPIC_API_KEY;
      if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not defined.");
      const modelName = model ?? DEFAULT_MODELS.anthropic;

      const anthropicConfig: any = {
        model: modelName,
        streaming,
        apiKey,
        ...extra,
      };

      // On Claude 4.7+ and 5.x, temperature/top_p causes HTTP 400
      // On Claude 4.5 class and 3.x, temperature is fully supported
      if (!isSamplingRestrictedAnthropic(modelName)) {
        anthropicConfig.temperature = temperature;
      }
      return new ChatAnthropic(anthropicConfig);
    }

    case "gemini":
    case "google":
    case "google-genai": {
      const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
      if (!apiKey) throw new Error("GEMINI_API_KEY is not defined.");
      const modelName = model ?? DEFAULT_MODELS.gemini;

      return new ChatGoogleGenerativeAI({
        model: modelName,
        temperature,
        streaming,
        apiKey,
        ...extra,
      });
    }

    default:
      throw new Error(`Unsupported provider: '${provider}'. Expected 'openai', 'anthropic', or 'gemini'.`);
  }
}

export interface CascadeOptions {
  primaryModel?: string;
  secondaryModel?: string;
  tertiaryModel?: string;
  temperature?: number;
}

export function getResilientCascade(options: CascadeOptions = {}) {
  const {
    primaryModel,
    secondaryModel,
    tertiaryModel,
    temperature = 0.0,
  } = options;

  const primary = getChatModel("anthropic", { model: primaryModel, temperature });
  const secondary = getChatModel("openai", { model: secondaryModel, temperature });
  const tertiary = getChatModel("gemini", { model: tertiaryModel, temperature });

  return primary.withFallbacks({
    fallbacks: [secondary, tertiary],
  });
}
