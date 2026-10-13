import test from "node:test";
import assert from "node:assert/strict";
import {
  calculateMultiModelCosts,
  recommendTieredRouting,
  calculateSemanticCacheROI,
  MODEL_CATALOG,
} from "./src/m06_gateways/costCalculator.js";
import {
  buildOpenRouterPayload,
  generateOpenRouterBatchSpec,
} from "./src/m06_gateways/openrouterIntegration.js";
import { getLiteLLMProxyClient } from "./src/m06_gateways/litellmProxyClient.js";
import {
  SubscriberDiagnosticSchema,
  getGatewayChatModel,
} from "./src/langchain_suite/m06_gateways/gatewayOrchestrator.js";

test("Cost Calculator calculates multi-model token economics correctly", () => {
  const result = calculateMultiModelCosts(1_000_000, 200_000);
  assert.equal(result.promptTokens, 1_000_000);
  assert.equal(result.completionTokens, 200_000);
  assert.ok(result.costs.length >= 4);

  // Check ordering from lowest to highest
  for (let i = 0; i < result.costs.length - 1; i++) {
    assert.ok(result.costs[i].totalCost <= result.costs[i + 1].totalCost);
  }

  // Fast economy model should be cheapest
  const cheapest = result.costs[0];
  assert.ok(cheapest.model.includes("flash") || cheapest.model.includes("mini") || cheapest.model.includes("haiku"));
});

test("Cost Calculator routes simple vs complex queries to appropriate tiers", () => {
  const simpleDecision = recommendTieredRouting("What is the APN setting for LTE roaming?");
  assert.equal(simpleDecision.recommendedTier, "FAST-ECONOMY");
  assert.ok(simpleDecision.estimatedCostPerMillion <= 1.0);

  const complexDecision = recommendTieredRouting(
    "Design a distributed zero-downtime database migration architecture for 50 million BSS subscriber profiles."
  );
  assert.equal(complexDecision.recommendedTier, "HIGH-REASONING");
  assert.ok(complexDecision.selectedModel.includes("sonnet") || complexDecision.selectedModel.includes("gpt-4o"));
});

test("Cost Calculator models semantic cache ROI with net savings", () => {
  const roi = calculateSemanticCacheROI("anthropic/claude-3.5-haiku", 100_000, 0.40);
  assert.equal(roi.cacheHitRate, 0.40);
  assert.ok(roi.netSavingsUsd > 0);
  assert.ok(roi.cacheCostUsd < roi.uncachedCostUsd);
});

test("OpenRouter payload builder formats fallback arrays and privacy policies", () => {
  const payload = buildOpenRouterPayload({
    messages: [{ role: "user", content: "Hello telecom gateway" }],
    primaryModel: "anthropic/claude-3.5-haiku",
    fallbackModels: ["google/gemini-flash-1.5", "openai/gpt-4o-mini"],
    denyDataCollection: true,
  });

  assert.equal(payload.model, "anthropic/claude-3.5-haiku");
  const extraBody = payload.extra_body as Record<string, any>;
  assert.ok(Array.isArray(extraBody.models));
  assert.deepEqual(extraBody.models, [
    "anthropic/claude-3.5-haiku",
    "google/gemini-flash-1.5",
    "openai/gpt-4o-mini",
  ]);
  assert.equal(extraBody.route, "fallback");
  assert.equal(extraBody.provider.data_collection, "deny");
});

test("OpenRouter batch spec generates valid asynchronous batch request", () => {
  const spec = generateOpenRouterBatchSpec();
  assert.equal(spec.endpoint, "/v1/chat/completions");
  assert.equal(spec.requests.length, 2);
  assert.equal(spec.provider.data_collection, "deny");
  assert.ok(spec.requests[0].custom_id.startsWith("req-telecom-ts"));
});

test("LiteLLM Proxy client initializes with custom or default virtual key endpoints", () => {
  const client = getLiteLLMProxyClient({
    proxyUrl: "http://gateway.telekom.internal:4000/v1",
    virtualKey: "sk-virtual-unit-test-key",
  });
  assert.equal(client.baseURL, "http://gateway.telekom.internal:4000/v1");
  assert.equal(client.apiKey, "sk-virtual-unit-test-key");
});

test("LangChain Gateway Orchestrator validates structured schemas and model targets", () => {
  // Validate schema
  const validDiagnostic = SubscriberDiagnosticSchema.parse({
    subscriberId: "SUB-49-170-001",
    planTier: "ENTERPRISE_5G",
    simStatus: "ACTIVE",
    recommendedAction: "No action required",
  });
  assert.equal(validDiagnostic.simStatus, "ACTIVE");

  // Invalid SIM status enum should throw
  assert.throws(() => {
    SubscriberDiagnosticSchema.parse({
      subscriberId: "SUB-49-170-002",
      planTier: "ENTERPRISE_5G",
      simStatus: "INVALID_STATUS",
      recommendedAction: "Unknown",
    });
  });

  // Test gateway model initialization
  const openrouterModel = getGatewayChatModel({ target: "openrouter" });
  assert.ok(openrouterModel);

  const litellmModel = getGatewayChatModel({ target: "litellm_proxy" });
  assert.ok(litellmModel);
});
