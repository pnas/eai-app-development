import pc from "picocolors";
import { getOpenAIClient, getAnthropicClient } from "./clientFactory.js";

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
  console.log(pc.magenta("\n=== Anthropic Tool Calling (TypeScript) ==="));
  const client = getAnthropicClient();

  const tools = [
    {
      name: "getServiceHealth",
      description: "Get real-time operational health metrics for an internal service.",
      input_schema: {
        type: "object" as const,
        properties: {
          serviceName: { type: "string" },
          environment: { type: "string", enum: ["staging", "production"] },
        },
        required: ["serviceName"],
      },
    },
  ];

  const messages: any[] = [
    { role: "user", content: "Check health of auth-service in production." },
  ];

  const response = await client.messages.create({
    model: "claude-3-5-haiku-20241022",
    max_tokens: 1024,
    tools,
    messages,
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
      model: "claude-3-5-haiku-20241022",
      max_tokens: 1024,
      messages,
    });

    const text = finalRes.content
      .filter((b) => b.type === "text")
      .map((b: any) => b.text)
      .join("");
    console.log(pc.bold("Final Answer:"), text);
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
}

main().catch(console.error);

