/**
 * Module 3: Google Gemini Context Caching (TypeScript).
 *
 * Demonstrates Google Gemini Enterprise Agent Platform Context Caching:
 * 1. Explicit Caching: Creating a CachedContent resource with custom TTL (min 1 min,
 *    default 60 min, no max duration), querying against it, and cleaning up.
 *    Provides 90% discount on Gemini 2.5+ models (75% on Gemini 2.0).
 *    Minimum token threshold: 2,048 tokens (Gemini 2 family) / 4,096 tokens (Gemini 3 family).
 * 2. Implicit Caching: Enabled by default across Google Cloud projects, providing
 *    an automatic 90% discount on cache hits with zero storage costs.
 * 3. Security & Isolation: Scoped by GCP project number, VPC Service Controls supported,
 *    and agentic context scoping to prevent cross-user leakage.
 */

import pc from "picocolors";
import { getGeminiClient } from "../m01_paradigms/clientFactory.js";

// Minimum token thresholds per Gemini Enterprise Agent Platform specs
export const GEMINI_2_MIN_CACHE_TOKENS = 2048;
export const GEMINI_3_MIN_CACHE_TOKENS = 4096;
export const GEMINI_3_IMPLICIT_PREVIEW_TOKENS = 6144;

function printImplicitCachingOverview(): void {
  console.log(pc.bold("\n=== Google Gemini Implicit Caching Overview ==="));
  console.log(
    `• ${pc.bold("Zero Configuration")}: Enabled by default across all Google Cloud projects.\n` +
    `• ${pc.bold("Discount")}: 90% discount on cached input tokens (same as explicit for Gemini 2.5+).\n` +
    `• ${pc.bold("Storage Cost")}: $0.00 (no storage costs for implicit caches).\n` +
    `• ${pc.bold("Thresholds")}:\n` +
    `   - Gemini 2 family: ${GEMINI_2_MIN_CACHE_TOKENS} tokens\n` +
    `   - Gemini 3 family: ${GEMINI_3_MIN_CACHE_TOKENS} tokens (6,144 tokens for 3.0 Flash Preview, 3.1 Pro Preview, 3.7 Flash, 3.8 Flash)\n` +
    `• ${pc.bold("Optimization Tips")}:\n` +
    `   1. Place large, common prompt content strictly at token index 0 (prefix).\n` +
    `   2. Send subsequent requests sharing the prefix in short temporal proximity.\n` +
    `• ${pc.bold("Agentic Isolation & Security")}:\n` +
    `   - Caches are isolated by GCP project number; never shared cross-project.\n` +
    `   - Scope multi-tenant agent caches to user execution context to prevent credential leakage.\n` +
    `   - Full VPC Service Controls (VPC-SC) support.`
  );
}

async function runGeminiExplicitCachingDemo(): Promise<void> {
  const client = getGeminiClient();
  const model = "gemini-2.5-flash";

  console.log(pc.bold("\n=== Google Gemini Explicit Context Caching ==="));
  console.log(
    `Target model: ${pc.cyan(model)} (Threshold: ${GEMINI_2_MIN_CACHE_TOKENS} tokens, 90% discount)`
  );

  // Generate synthetic content meeting the Gemini 2 minimum threshold (>= 2,048 tokens)
  const baseText =
    "Telekom Enterprise Network Infrastructure Specification v4.2. " +
    "Core node cluster policy IP: 10.240.0.1. Failover gateway: 10.240.0.254. " +
    "BGP Autonomous System Number: AS65001. VLAN ID: 4094. " +
    "Latency SLA requirement: sub-5ms within regional metro area. ";

  const largeContent = baseText.repeat(100);
  const wordCount = largeContent.split(/\s+/).length;

  console.log(
    `Generated context payload (~${wordCount} words, >${GEMINI_2_MIN_CACHE_TOKENS} tokens).`
  );
  console.log("Creating explicit Cache resource via client.caches.create()...");

  try {
    // Explicit cache creation: TTL 10 minutes (min 1 min, default 60 min, no max duration)
    // Max content size: 10 MB for text/blob
    const cache = await client.caches.create({
      model,
      config: {
        contents: [largeContent],
        systemInstruction: "You are a telecom infrastructure engineering assistant referencing this network spec.",
        ttl: "600s",
        displayName: "telekom_network_spec_cache_v4",
      },
    });

    console.log(
      pc.green(`Cache created successfully! Name: ${cache.name}, Expires: ${cache.expireTime}`)
    );

    console.log("Querying Gemini using explicit cachedContent reference...");
    const response = await client.models.generateContent({
      model,
      contents: "What is the core node cluster policy IP and failover gateway mentioned in the document?",
      config: {
        cachedContent: cache.name,
      },
    });

    console.log(pc.bold("Response:"), response.text);

    if (response.usageMetadata) {
      const promptCount = response.usageMetadata.promptTokenCount ?? 0;
      const cachedCount = response.usageMetadata.cachedContentTokenCount ?? 0;
      console.log(
        pc.green(`Usage Metadata: Prompt Tokens: ${promptCount}, Cached Tokens Read: ${cachedCount}`)
      );
    }

    // Clean up cache resource
    if (cache.name) {
      await client.caches.delete({ name: cache.name });
      console.log(pc.gray("Cache resource deleted successfully."));
    }
  } catch (err: any) {
    console.log(
      pc.yellow(
        `Explicit context caching notice (requires GCP billing/tier and >=${GEMINI_2_MIN_CACHE_TOKENS} tokens): ${err.message}`
      )
    );
  }
}

async function main(): Promise<void> {
  printImplicitCachingOverview();
  await runGeminiExplicitCachingDemo();
}

main().catch(console.error);
