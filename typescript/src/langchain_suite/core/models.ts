import "dotenv/config";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { ChatOpenAI } from "@langchain/openai";
import { ChatAnthropic } from "@langchain/anthropic";
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";

export interface ChatModelOptions {
  model?: string;
  temperature?: number;
  streaming?: boolean;
}

export function getChatModel(
  provider: "openai" | "anthropic" | "gemini" = "openai",
  options: ChatModelOptions = {}
): BaseChatModel {
  const { model, temperature = 0.0, streaming = true } = options;

  switch (provider.toLowerCase()) {
    case "openai": {
      const apiKey = process.env.OPENAI_API_KEY;
      if (!apiKey) throw new Error("OPENAI_API_KEY is not defined.");
      return new ChatOpenAI({
        model: model ?? "gpt-4o-mini",
        temperature,
        streaming,
        apiKey,
      });
    }

    case "anthropic":
    case "claude": {
      const apiKey = process.env.ANTHROPIC_API_KEY;
      if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not defined.");
      return new ChatAnthropic({
        model: model ?? "claude-3-5-haiku-20241022",
        temperature,
        streaming,
        apiKey,
      });
    }

    case "gemini":
    case "google": {
      const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
      if (!apiKey) throw new Error("GEMINI_API_KEY is not defined.");
      return new ChatGoogleGenerativeAI({
        model: model ?? "gemini-2.0-flash",
        temperature,
        streaming,
        apiKey,
      });
    }

    default:
      throw new Error(`Unsupported provider: '${provider}'. Expected 'openai', 'anthropic', or 'gemini'.`);
  }
}

export function getResilientCascade(temperature = 0.0) {
  const primary = getChatModel("anthropic", { temperature });
  const secondary = getChatModel("openai", { temperature });
  const tertiary = getChatModel("gemini", { temperature });

  return primary.withFallbacks({
    fallbacks: [secondary, tertiary],
  });
}

