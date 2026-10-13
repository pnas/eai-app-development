/**
 * Module 1: Tool / Function Calling Wire Protocol Mechanics (TypeScript)
 *
 * Demonstrates the 2-step wire round-trip (model emits function_call/tool_use,
 * client executes local logic and sends tool_result/functionResponse back)
 * across OpenAI, Anthropic, and Google Gemini.
 *
 * Official References:
 * - Anthropic Working with Messages: https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 * - Anthropic Effort Controls: https://platform.claude.com/docs/en/build-with-claude/effort
 * - Anthropic Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
 * - OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
 * - Google Gemini Models: https://ai.google.dev/gemini-api/docs/models
 * - Google Gemini Streaming: https://ai.google.dev/gemini-api/docs/streaming
 * - Google Gemini Interactions API: https://ai.google.dev/gemini-api/docs/interactions-overview
 * - Google GenAI Function Calling: https://ai.google.dev/gemini-api/docs/function-calling
 */

import pc from "picocolors";
import { getOpenAIClient, getAnthropicClient, getGeminiClient } from "./clientFactory.js";

function getServiceHealth(serviceName: string, environment: string = "production") {
  return {
    service: serviceName,
    environment,
    status: "HEALTHY",
    latency_ms: 22.4,
    active_replicas: 4,
  };
}

async function demoOpenAIToolCall() {
  console.log(pc.cyan("\n=== OpenAI Tool Calling (TypeScript) ==="));
  const client = getOpenAIClient();

  const tools = [
    {
      type: "function" as const,
      function: {
        name: "getServiceHealth",
        description: "Get real-time operational health metrics for an internal service.",
        parameters: {
          type: "object",
          properties: {
            serviceName: { type: "string" },
            environment: { type: "string", enum: ["staging", "production"] },
          },
          required: ["serviceName"],
          additionalProperties: false,
        },
        strict: true,
      },
    },
  ];

  const messages: any[] = [
    { role: "user", content: "Is the billing-service healthy in production?" },
  ];

  const response = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
    tools,
  });

  const msg = response.choices[0]?.message;
  if (msg?.tool_calls && msg.tool_calls.length > 0) {
    const toolCall = msg.tool_calls[0];
    const args = JSON.parse(toolCall.function.arguments);
    console.log(pc.green(`OpenAI invoked: ${toolCall.function.name}`), args);

    const result = getServiceHealth(args.serviceName, args.environment);

    messages.push(msg);
    messages.push({
      role: "tool",
      tool_call_id: toolCall.id,
      content: JSON.stringify(result),
    });

    const finalRes = await client.chat.completions.create({
      model: "gpt-4o-mini",
      messages,
    });
    console.log(pc.bold("Final Answer:"), finalRes.choices[0]?.message?.content);
  }
}

async function demoAnthropicToolCall() {
  console.log(pc.magenta("\n=== Anthropic Tool Calling (Claude Haiku 5.5 TypeScript) ==="));
  const client = getAnthropicClient();

  const tools = [
    {
      name: "getServiceHealth",
      description: "Get real-time operational health metrics for an internal service.",
      strict: true,
      input_schema: {
        type: "object" as const,
        properties: {
          serviceName: { type: "string" },
          environment: { type: "string", enum: ["staging", "production"] },
        },
        required: ["serviceName"],
        additionalProperties: false,
      },
    },
  ];

  const messages: any[] = [
    { role: "user", content: "Check health of auth-service in production." },
  ];

  const response = await client.messages.create({
    model: "claude-haiku-5-5",
    max_tokens: 1024,
    tools,
    messages,
    ...( { output_config: { effort: "medium" } } as any ),
  });

  const toolUse = response.content.find((b) => b.type === "tool_use") as any;
  if (toolUse) {
    console.log(pc.green(`Anthropic invoked: ${toolUse.name}`), toolUse.input);
    const result = getServiceHealth(toolUse.input.serviceName, toolUse.input.environment);

    messages.push({ role: "assistant", content: response.content });
    messages.push({
      role: "user",
      content: [
        {
          type: "tool_result",
          tool_use_id: toolUse.id,
          content: JSON.stringify(result),
        },
      ],
    });

    const finalRes = await client.messages.create({
      model: "claude-haiku-5-5",
      max_tokens: 1024,
      messages,
      ...( { output_config: { effort: "medium" } } as any ),
    });

    const text = finalRes.content
      .filter((b) => b.type === "text")
      .map((b: any) => b.text)
      .join("");
    console.log(pc.bold("Final Answer:"), text);
  }
}

async function demoGeminiToolCall() {
  console.log(pc.green("\n=== Google Gemini Tool Calling Wire Protocol (TypeScript) ==="));
  const client = getGeminiClient();
  const model = "gemini-3.8-flash";

  const toolDeclaration = {
    name: "getServiceHealth",
    description: "Get real-time operational health metrics for an internal service.",
    parameters: {
      type: "OBJECT" as const,
      properties: {
        serviceName: { type: "STRING" as const, description: "e.g. auth-service, billing" },
        environment: { type: "STRING" as const, enum: ["staging", "production"] },
      },
      required: ["serviceName"],
    },
  };

  const contents: any[] = [
    {
      role: "user",
      parts: [{ text: "Check health of db-service in production." }],
    },
  ];

  const response = await client.models.generateContent({
    model,
    contents,
    config: {
      tools: [{ functionDeclarations: [toolDeclaration as any] }],
    },
  });

  const functionCalls = response.functionCalls;
  if (functionCalls && functionCalls.length > 0) {
    const call = functionCalls[0];
    console.log(pc.green(`Gemini invoked: ${call.name}`), call.args);

    const args = (call.args || {}) as { serviceName: string; environment?: string };
    const result = getServiceHealth(args.serviceName, args.environment);

    // Append model function call turn
    if (response.candidates?.[0]?.content) {
      contents.push(response.candidates[0].content);
    }

    // Append user/tool functionResponse turn
    contents.push({
      role: "user",
      parts: [
        {
          functionResponse: {
            name: call.name,
            response: { result },
          },
        },
      ],
    });

    const finalRes = await client.models.generateContent({
      model,
      contents,
      config: {
        tools: [{ functionDeclarations: [toolDeclaration as any] }],
      },
    });

    console.log(pc.bold("Final Answer:"), finalRes.text);
  }
}

async function main() {
  try {
    await demoOpenAIToolCall();
  } catch (err: any) {
    console.log(pc.red(`OpenAI Tool error: ${err.message}`));
  }

  try {
    await demoAnthropicToolCall();
  } catch (err: any) {
    console.log(pc.red(`Anthropic Tool error: ${err.message}`));
  }

  try {
    await demoGeminiToolCall();
  } catch (err: any) {
    console.log(pc.red(`Gemini Tool error: ${err.message}`));
  }
}

main().catch(console.error);

