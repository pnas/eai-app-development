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

# 1. Realtime vs. Batch Processing

| Metric | Realtime API (`/v1/chat/completions`) | Batch API (`/v1/batches`) |
| :--- | :--- | :--- |
| **Turnaround SLA** | 500ms – 5 seconds | 24 hours (typically minutes to hours) |
| **Pricing** | Standard 100% token price | **Flat 50% discount** on all tokens |
| **Rate Limit Impact** | Consumes strict RPM / TPM quotas | Separate, massive batch quotas |
| **Ideal Workloads** | Live chatbots, interactive agents | Backfilling, evals, classification, ETL |

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

- Each row in the `.jsonl` input must have a unique `custom_id`.
- The `custom_id` allows the application to re-correlate outputs back to database records even if completed out of order.

---

# 3. Code Walkthrough: OpenAI Batch API

```python
# 1. Upload JSONL File
file_obj = client.files.create(
    file=open("batch_requests.jsonl", "rb"),
    purpose="batch"
)

# 2. Submit Batch Job
batch_job = client.batches.create(
    input_file_id=file_obj.id,
    endpoint="/v1/chat/completions",
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

# 4. Error Handling in Batch Processing

Batch jobs introduce two levels of errors:

1. **Job-Level Failure**:
   - The entire batch is rejected (e.g. malformed JSONL syntax, invalid model ID, file expired).
   - Inspected via `batch_job.errors`.

2. **Row-Level Failure**:
   - The batch completes, but individual rows fail (e.g. content policy violation, schema error).
   - Inspected via the separate `error_file_id` output stream.

**Production Pattern**: Always inspect both `output_file_id` and `error_file_id`, and push failed rows to a Dead-Letter Queue (DLQ).

