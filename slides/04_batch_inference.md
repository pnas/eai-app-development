---
marp: true
theme: default
paginate: true
header: "Advanced GenAI Integration | Module 4"
footer: "Enterprise AI Engineering Course"
---

# Module 4: Asynchronous Batch Inference at Scale
## 50% Cost Reductions, State Machines & High-Throughput Processing

---

# 1. Realtime, Flex & Batch Processing Compared

| Dimension | Standard Sync (`service_tier: "default"`) | Flex Processing (`service_tier: "flex"`) | Batch API (`/v1/batches`) |
| :--- | :--- | :--- | :--- |
| **API Pattern** | Synchronous REST / SSE | **Synchronous REST / SSE** | Asynchronous JSONL upload |
| **Turnaround SLA** | Sub-second – 5 seconds | Seconds to minutes (timeout up to 15m) | 24 hours turnaround window |
| **Pricing** | 100% standard token price | **50% discount** (same as Batch!) | **50% discount** on all tokens |
| **Quota Impact** | Standard RPM / TPM | Standard or Flex RPM / TPM | Dedicated Batch token queues |
| **Endpoints** | `/v1/responses`, `/v1/chat/completions` | `/v1/responses`, `/v1/chat/completions` | `/v1/responses`, `/v1/chat/completions` |
| **Ideal Workloads** | Interactive user-facing chat | Non-blocking synchronous workers, ETL | Massive offline pipelines, bulk evals |

---

# 2. The Batch Processing Lifecycle

```
1. Format JSONL ────► 2. Upload File ────► 3. Create Batch Job
                             │                     │
                             ▼                     ▼
                      File Object ID          Batch ID
                                                   │
                                                   ▼
4. Download Output ◄── 5. Status: Completed ◄── 4. Polling Loop
   (JSONL Stream)                                (Exp. Backoff)
```

- Input rows support both `/v1/responses` and `/v1/chat/completions`.
- Each row in `.jsonl` requires a unique `custom_id` for out-of-order re-correlation.
- Output contains `output_file_id` (successes) and `error_file_id` (failures).

---

# 3. Code Walkthrough: OpenAI Batch API

```python
# 1. Upload JSONL File
file_obj = client.files.create(
    file=open("batch_requests.jsonl", "rb"),
    purpose="batch"
)

# 2. Submit Batch Job for Responses API or Chat Completions
batch_job = client.batches.create(
    input_file_id=file_obj.id,
    endpoint="/v1/responses",  # or "/v1/chat/completions"
    completion_window="24h"
)

# 3. Poll with Exponential Backoff
while True:
    status = client.batches.retrieve(batch_job.id)
    if status.status in ("completed", "failed", "cancelled"):
        break
    time.sleep(30)
```

---

# 4. Flex Processing: 50% Off Without Asynchronous Pipelines

When tasks don't require an immediate sub-second response, use `service_tier="flex"`:

```python
# Synchronous call with 50% discount via Flex Processing
response = client.responses.create(
    model="gpt-6.1-sol",
    input="Perform comprehensive analysis of quarterly financial report...",
    service_tier="flex",
    timeout=900.0  # Allow up to 15 minutes for flex processing
)
```

**Key Engineering Guidelines for Flex Processing**:
1. **Extend Client Timeouts**: Set HTTP timeouts to 10–15 minutes (default 60s will time out).
2. **Handle 429 Resource Unavailable**: If flex capacity is temporarily constrained, retry with exponential backoff or fall back to `service_tier: "default"`.
3. **No File Management Overhead**: Avoids JSONL formatting, S3/OpenAI file uploads, polling loops, and multi-file reconciliation.

---

# 5. Error Handling in Batch Processing

Batch jobs introduce two levels of errors:

1. **Job-Level Failure**:
   - The entire batch is rejected (e.g. malformed JSONL syntax, invalid model ID, file expired).
   - Inspected via `batch_job.errors`.

2. **Row-Level Failure**:
   - The batch completes, but individual rows fail (e.g. content policy violation, schema error).
   - Inspected via the separate `error_file_id` output stream.

**Production Pattern**: Always inspect both `output_file_id` and `error_file_id`, and push failed rows to a Dead-Letter Queue (DLQ).

---

# 6. Official Documentation & References

- **OpenAI Batch API Guide**: https://developers.openai.com/api/docs/guides/batch
- **OpenAI Flex Processing Guide**: https://developers.openai.com/api/docs/guides/flex-processing
- **OpenAI Latency Optimization**: https://developers.openai.com/api/docs/guides/latency-optimization


