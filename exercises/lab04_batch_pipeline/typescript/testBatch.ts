import test from "node:test";
import assert from "node:assert/strict";
import { BatchPipeline } from "./solution.js";

test("BatchPipeline generates compliant JSONL", () => {
  const items = [
    { id: "req-001", prompt: "Summarize transcript 1" },
    { id: "req-002", prompt: "Extract entities from transcript 2" },
  ];

  const jsonl = BatchPipeline.generateBatchJsonl(items, "gpt-4o-mini");
  const lines = jsonl.trim().split("\n");
  assert.equal(lines.length, 2);

  const parsed0 = JSON.parse(lines[0]);
  assert.equal(parsed0.custom_id, "req-001");
  assert.equal(parsed0.method, "POST");
  assert.equal(parsed0.url, "/v1/chat/completions");
  assert.equal(parsed0.body.messages[0].content, "Summarize transcript 1");
});

test("BatchPipeline processes mixed results with line error isolation and 50% savings", () => {
  const mockJsonl = [
    JSON.stringify({
      custom_id: "req-001",
      response: {
        status_code: 200,
        body: {
          choices: [{ message: { content: "Summary 1" } }],
          usage: { prompt_tokens: 1000, completion_tokens: 200 },
        },
      },
    }),
    JSON.stringify({
      custom_id: "req-002",
      error: { code: "content_policy_violation", message: "Safety filter triggered" },
    }),
    JSON.stringify({
      custom_id: "req-003",
      response: {
        status_code: 200,
        body: {
          choices: [{ message: { content: "Summary 3" } }],
          usage: { prompt_tokens: 3000, completion_tokens: 800 },
        },
      },
    }),
  ].join("\n");

  const { results, summary } = BatchPipeline.processBatchResults(mockJsonl, "gpt-4o-mini");

  assert.equal(summary.successfulItems, 2);
  assert.equal(summary.failedItems, 1);
  assert.equal(summary.totalPromptTokens, 4000);
  assert.equal(summary.totalCompletionTokens, 1000);

  // Line isolation
  assert.equal(results["req-001"].status, "success");
  assert.equal(results["req-001"].content, "Summary 1");
  assert.equal(results["req-002"].status, "error");
  assert.equal(results["req-003"].status, "success");

  // Financial accounting
  // 4000 * 0.15/1M = 0.0006
  // 1000 * 0.60/1M = 0.0006
  // Total std = 0.0012
  // Batch 50% = 0.0006
  assert.equal(summary.standardCostUsd, 0.0012);
  assert.equal(summary.batchDiscountedCostUsd, 0.0006);
  assert.equal(summary.netSavingsUsd, 0.0006);
});

