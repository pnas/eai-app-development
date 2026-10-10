import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";

const LARGE_POLICY_DOC = `
# TELEKOM ENTERPRISE CLOUD GOVERNANCE & RESILIENCE MANUAL (v4.2)
[Section 1: Distributed Architecture Standards]
All microservices must implement distributed tracing with OpenTelemetry and propagate W3C trace context.
All internal synchronous RPCs must enforce timeouts of max 1,500ms and retry only on idempotency-safe methods.
[Section 2: Database and Sharding Architecture]
PostgreSQL instances must be provisioned across at least 3 Availability Zones with automatic failover.
Write operations must never bypass the primary leader node. Read replicas must be load-balanced with max replication lag of 250ms.
[Section 3: Security & Data Classification]
PII (Personally Identifiable Information) must be encrypted at rest with customer-managed KMS keys.
All API endpoints exposed to the public internet must enforce TLS 1.3 with mutual authentication for B2B partners.
`.concat("\nAll microservices must undergo chaos testing quarterly and verify graceful degradation under 50% packet loss.\n".repeat(50));

async function runAnthropicCachingDemo() {
  const client = getAnthropicClient();
  const model = "claude-3-5-sonnet-20241022";

  console.log(pc.bold("\n=== Anthropic Prompt Caching (TypeScript) ===\n"));

  const systemWithCache: any = [
    {
      type: "text",
      text: LARGE_POLICY_DOC,
      cache_control: { type: "ephemeral" }, // <-- Breakpoint
    },
  ];

  const queries = [
    "What is the maximum allowed replication lag for read replicas?",
    "What are the quarterly testing requirements for microservices?",
  ];

  const conversationHistory: any[] = [];

  for (let i = 0; i < queries.length; i++) {
    const q = queries[i];
    conversationHistory.push({ role: "user", content: q });

    const start = performance.now();
    const response = await client.messages.create({
      model,
      max_tokens: 256,
      system: systemWithCache,
      messages: conversationHistory,
    });
    const elapsed = ((performance.now() - start) / 1000).toFixed(2);

    const usage: any = response.usage;
    const writeTok = usage.cache_creation_input_tokens ?? 0;
    const readTok = usage.cache_read_input_tokens ?? 0;

    console.log(
      pc.cyan(`Turn ${i + 1}: `) +
      pc.yellow(`WriteTok: ${writeTok} | `) +
      pc.green(`ReadTok (Hit): ${readTok} | `) +
      pc.magenta(`Latency: ${elapsed}s`)
    );

    conversationHistory.push({ role: "assistant", content: response.content });
  }

  console.log(pc.gray("\nNotice: Turn 1 creates the cache. Turn 2 achieves a 90% discount on cached tokens with faster TTFT!\n"));
}

runAnthropicCachingDemo().catch(console.error);

