/**
 * Lab 04 TypeScript Reference Solution: Batch API Cost Arbitrage Pipeline.
 */

import { BatchItem, CostSummary } from "./starter.js";

export { BatchItem, CostSummary };

export class BatchPipeline {
  public static readonly STANDARD_RATES: Record<string, { prompt: number; completion: number }> = {
    "gpt-4o-mini": { prompt: 0.15 / 1_000_000, completion: 0.60 / 1_000_000 },
    "gpt-4o": { prompt: 2.50 / 1_000_000, completion: 10.00 / 1_000_000 },
  };

  public static generateBatchJsonl(items: BatchItem[], model = "gpt-4o-mini"): string {
    return items
      .map((item) =>
        JSON.stringify({
          custom_id: item.id,
          method: "POST",
          url: "/v1/chat/completions",
          body: {
            model,
            messages: [{ role: "user", content: item.prompt }],
          },
        })
      )
      .join("\n");
  }

  public static processBatchResults(
    resultsJsonl: string,
    model = "gpt-4o-mini"
  ): { results: Record<string, any>; summary: CostSummary } {
    const results: Record<string, any> = {};
    let promptTokens = 0;
    let completionTokens = 0;
    let successfulItems = 0;
    let failedItems = 0;

    const lines = resultsJsonl.trim().split("\n");
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      const record = JSON.parse(line);
      const cid = record.custom_id || "unknown";

      if (record.error) {
        failedItems++;
        results[cid] = { status: "error", error: record.error };
        continue;
      }

      const response = record.response || {};
      const statusCode = response.status_code || 500;

      if (statusCode !== 200) {
        failedItems++;
        results[cid] = { status: "error", statusCode, body: response.body };
        continue;
      }

      const body = response.body || {};
      const choices = body.choices || [];
      const content = choices[0]?.message?.content || "";

      const usage = body.usage || {};
      promptTokens += usage.prompt_tokens || 0;
      completionTokens += usage.completion_tokens || 0;
      successfulItems++;

      results[cid] = { status: "success", content };
    }

    const rates = this.STANDARD_RATES[model] || this.STANDARD_RATES["gpt-4o-mini"];
    const standardCostUsd = Number(
      (promptTokens * rates.prompt + completionTokens * rates.completion).toFixed(6)
    );
    const batchDiscountedCostUsd = Number((standardCostUsd * 0.5).toFixed(6));
    const netSavingsUsd = Number((standardCostUsd - batchDiscountedCostUsd).toFixed(6));

    const summary: CostSummary = {
      totalPromptTokens: promptTokens,
      totalCompletionTokens: completionTokens,
      standardCostUsd,
      batchDiscountedCostUsd,
      netSavingsUsd,
      successfulItems,
      failedItems,
    };

    return { results, summary };
  }
}

