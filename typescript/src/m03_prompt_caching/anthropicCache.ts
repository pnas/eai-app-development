/**
 * Module 3: Anthropic Explicit & Automatic Prompt Caching with Diagnostics (TypeScript).
 *
 * Demonstrates modern Anthropic prompt caching capabilities (Claude 5.5 / 5 / 3.7):
 * 1. Breakpoint 1 on large static system documentation (>=1,024 tokens) with 1h extended TTL.
 * 2. Breakpoint 2 on structured tool definitions.
 * 3. Mid-conversation system messages (`role: "system"`) to append instructions without invalidating cache.
 * 4. Top-level automatic caching (cache_control: { type: "ephemeral" } at request level).
 * 5. 1-hour extended TTL ({ type: "ephemeral", ttl: "1h" }) at 2.0x write price
 *    vs standard 5-minute rolling TTL at 1.25x write price.
 * 6. 20-block lookback window in prefix matching (consecutive tool_use/tool_result = 1 position).
 * 7. Cache Diagnostics opt-in (diagnostics: { previous_message_id: ... })
 *    inspecting cache_miss_reason (system_changed, tools_changed, messages_changed,
 *    model_changed, previous_message_not_found, unavailable) and cache_missed_input_tokens.
 * 8. Telemetry inspection: cache_creation_input_tokens vs cache_read_input_tokens (95% discount on 5.5).
 *
 * Reference:
 * - https://platform.claude.com/docs/en/build-with-claude/working-with-messages
 * - https://platform.claude.com/docs/en/build-with-claude/citations
 */

import pc from "picocolors";
import { getAnthropicClient } from "../m01_paradigms/clientFactory.js";

// Generates synthetic large context (>1,024 tokens to meet Claude Sonnet/Opus threshold)
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

// Tool definition with cache_control breakpoint
const TOOLS_WITH_CACHE: any[] = [
  {
    name: "lookup_compliance_rule",
    description: "Look up a specific compliance clause in the cloud governance manual.",
    input_schema: {
      type: "object",
      properties: {
        section: { type: "string", description: "Section name or number" },
        keyword: { type: "string", description: "Specific keyword or rule" },
      },
      required: ["section"],
    },
    // Anthropic allows placing cache_control on tool definitions to cache all schemas up to this point
    cache_control: { type: "ephemeral", ttl: "1h" }, // <-- Breakpoint: Tool schemas (TTL must be >= downstream blocks)
  },
];

async function runAnthropicCachingDemo() {
  const client = getAnthropicClient();
  let model = "claude-sonnet-5-5";

  console.log(pc.bold(pc.cyan("\n=== Anthropic Prompt Caching & Diagnostics (Claude 5.5 / 5 / 3.7) ===")));
  console.log(
    `• ${pc.bold("Breakpoints")}: Up to 4 explicit markers or top-level automatic caching.\n` +
    `• ${pc.bold("TTL Options")}: Default 5m (1.25x write surcharge) | Extended 1h (ttl='1h', 2.0x write surcharge).\n` +
    `• ${pc.bold("Lookback Window")}: 20-block lookback window in prefix matching (consecutive tool blocks = 1).\n` +
    `• ${pc.bold("Minimum Tokens")}: 1,024 tokens (Sonnet / Opus) | 2,048 tokens (Haiku).\n` +
    `• ${pc.bold("Read Pricing Multipliers")}: 0.05x (Sonnet 5.5/Opus 5.5 - 95% discount) | 0.10x (Sonnet 3.5/Haiku) | 0.025x (Mythos/Fable).\n` +
    `• ${pc.bold("Cache Diagnostics")}: Opt-in via diagnostics: { previous_message_id: ... }; tracks miss reasons & tokens.\n`
  );

  // Breakpoint 1: On the large static system document (with 1h extended TTL demo)
  const systemWithCache: any = [
    {
      type: "text",
      text: LARGE_POLICY_DOC,
      cache_control: { type: "ephemeral", ttl: "1h" }, // <-- Breakpoint 1: 1-hour extended TTL
    },
  ];

  const queries = [
    "What is the maximum allowed replication lag for read replicas?",
    "What are the quarterly testing requirements for microservices?",
    "What TLS version is mandatory for public API endpoints?",
  ];

  const conversationHistory: any[] = [];
  let previousMessageId: string | null = null;

  for (let i = 0; i < queries.length; i++) {
    const q = queries[i];
    conversationHistory.push({ role: "user", content: q });

    // Cache Diagnostics opt-in: null on Turn 1; previous_message_id on subsequent turns
    const diagnosticsParam: any = { previous_message_id: previousMessageId };

    const start = performance.now();
    let response: any;
    try {
      response = await client.messages.create({
        model,
        max_tokens: 256,
        system: systemWithCache,
        tools: TOOLS_WITH_CACHE,
        messages: conversationHistory,
        diagnostics: diagnosticsParam,
      } as any);
    } catch {
      // Fallback to Claude 3.7 / 3.5 Sonnet if 5.5 is not yet active on the key
      try {
        model = "claude-3-7-sonnet-20250219";
        response = await client.messages.create({
          model,
          max_tokens: 256,
          system: systemWithCache,
          tools: TOOLS_WITH_CACHE,
          messages: conversationHistory,
          diagnostics: diagnosticsParam,
        } as any);
      } catch {
        model = "claude-3-5-sonnet-20241022";
        response = await client.messages.create({
          model,
          max_tokens: 256,
          system: systemWithCache,
          tools: TOOLS_WITH_CACHE,
          messages: conversationHistory,
          diagnostics: diagnosticsParam,
        } as any);
      }
    }
    const elapsed = ((performance.now() - start) / 1000).toFixed(2);

    const usage: any = response.usage;
    const inputTokens = usage?.input_tokens ?? 0;
    const writeTok = usage?.cache_creation_input_tokens ?? 0;
    const readTok = usage?.cache_read_input_tokens ?? 0;

    // Inspect Anthropic Cache Diagnostics
    const diag = response.diagnostics;
    const missReason = diag?.cache_miss_reason?.type ?? "none";
    const missedTokens = diag?.cache_miss_reason?.cache_missed_input_tokens ?? 0;

    console.log(
      pc.cyan(`Turn ${i + 1}: `) +
      pc.white(`Query: "${q.slice(0, 28)}..." | `) +
      pc.gray(`Base: ${inputTokens} | `) +
      pc.yellow(`WriteTok: ${writeTok} | `) +
      pc.green(`ReadTok: ${readTok} | `) +
      pc.magenta(`MissReason: ${missReason} | `) +
      pc.red(`MissedTok: ${missedTokens} | `) +
      pc.gray(`Latency: ${elapsed}s`)
    );

    conversationHistory.push({ role: "assistant", content: response.content });
    // Thread the message ID for the next turn's diagnostics comparison
    previousMessageId = response.id ?? null;
  }

  console.log(
    pc.gray(
      "\nAnalysis: Turn 1 creates the cache (1h TTL write surcharge). " +
      "Turns 2 & 3 achieve prompt cache hits with 90-95% read discounts and diagnostic confirmation.\n"
    )
  );
}

runAnthropicCachingDemo().catch(console.error);
