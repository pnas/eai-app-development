# Lab 04: Batch API Cost Arbitrage Pipeline

## Problem Statement
Your team is tasked with backfilling and classifying 100,000 historical support transcripts.
Executing this pipeline against real-time `/v1/chat/completions`:
- Competes with live customer chat traffic for rate limit quotas (TPM/RPM).
- Costs \$2,500 at standard pricing.
- Suffers socket drops and retry storms under long-running batch jobs.

By migrating to the **Asynchronous Batch API**:
- You receive a **guaranteed 50% discount** on all token billing (\$1,250 net savings).
- Batch requests utilize a separate, dedicated backend processing pool without impacting live user quotas.
- Work is isolated line-by-line; an invalid transcript does not fail the batch.

---

## Lab Objectives

1. **Compliant JSONL Generation**:
   Implement `generate_batch_jsonl()` to serialize records into valid provider batch schemas with unique `custom_id` tracking.
2. **Line-Level Fault Isolation**:
   Implement `process_batch_results()` to parse output JSONL files, handling mixed results (successful responses vs per-line HTTP errors) without throwing unhandled exceptions.
3. **Audited Financial Reconciler**:
   Calculate exact token consumption (prompt vs completion), comparing standard on-demand cost against the 50% batch rate, and reporting net corporate savings.

---

## Instructions

### Python
- Starter code: `python/starter.py`
- Run tests:
  ```powershell
  uv run pytest exercises/lab04_batch_pipeline/python/test_batch.py
  ```

### TypeScript
- Starter code: `typescript/starter.ts`
- Run tests:
  ```powershell
  npx tsx --test exercises/lab04_batch_pipeline/typescript/testBatch.ts
  ```

