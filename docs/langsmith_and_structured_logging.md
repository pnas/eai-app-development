# Architecture Guide: LangSmith Tracing & Enterprise Structured Logging

This document details how **LangSmith** integrates into production LangChain and LangGraph architectures, and how enterprises run **standard structured application logging** (Python `logging` / `structlog`, TypeScript `pino` / `winston` / `console`) in parallel to capture deep agent internals, satisfy audit compliance, and preserve observability across air-gapped or hybrid environments.

---

## 1. Executive Summary & The Dual-Telemetry Paradigm

Modern enterprise AI deployments require two distinct observability streams that serve different stakeholders:

| Telemetry Stream | Primary Audience | Ingestion Mechanism | Key Capabilities | Enterprise Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **LangSmith Tracing** | AI Engineers, Data Scientists, Product Managers | Non-blocking background HTTPS worker (`api.smith.langchain.com` or private VPC instance) | Hierarchical run trees, token cost analytics, prompt playgrounds, human-in-the-loop feedback, golden datasets, regression evals | Model drift detection, prompt iteration, prompt-to-output evaluation, agent trajectory debugging |
| **Enterprise Structured Logging** | SecOps, Cloud Platform Engineers, DevOps, Compliance Officers | In-band synchronous or local stream to stdout/stderr (ingested by Fluentbit/Vector into Splunk, Elastic, Datadog) | High-throughput structured JSON, deterministic PII redaction, SIEM correlation, network air-gap compliance, alert triggers | GDPR/EU AI Act audit logs, infrastructure health, network failures, incident forensics, data loss prevention (DLP) |

Rather than choosing one over the other, production systems implement a **Dual-Telemetry Architecture**:
- **LangSmith** captures the semantic AI lifecycle and agent graph steps.
- **Structured Logging** captures operational internals, correlation headers, state transitions, and audit records with strict PII filtering.

```
                           +-----------------------------------------------+
                           |            Incoming User Request              |
                           +-----------------------------------------------+
                                                  |
                                                  v
                           +-----------------------------------------------+
                           |         LangGraph Agent State Machine         |
                           |   (Nodes, Edges, State Annotations, Checkpoint)|
                           +-----------------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |     Callback Dispatcher Subsystem   |
                               +-------------------------------------+
                                    /                           \
                                   /                             \
        Path A: Distributed Tracing                               Path B: Application Logging
                                 v                                         v
       +------------------------------------+             +----------------------------------+
       | LangSmith Tracer (Async Transport) |             | StructuredLoggingCallbackHandler |
       +------------------------------------+             +----------------------------------+
                         |                                                 |
                         v                                                 v
       +------------------------------------+             +----------------------------------+
       |   Non-blocking Background Queue    |             | PII Sanitizer & Context Enforcer |
       +------------------------------------+             +----------------------------------+
                         |                                                 |
                         v                                                 v
       +------------------------------------+             +----------------------------------+
       | LangSmith SaaS / Self-Hosted       |             | Local stdout / JSON Stream       |
       | - Run Tree (Graph -> Node -> LLM)  |             | - ECS / Splunk / Datadog Format  |
       | - Token Cost Attribution           |             | - thread_id, run_id, latency_ms  |
       | - Online Evals & Datasets          |             | - Masked Tool Inputs & Outputs   |
       +------------------------------------+             +----------------------------------+
```

---

## 2. How LangSmith Fits into LangChain & LangGraph

### 2.1 The Run Tree Hierarchy
In LangChain and LangGraph, every execution is modeled as a directed acyclic graph of **Runs** (spans). A run has a `name`, `run_type` (`chain`, `llm`, `tool`, `prompt`), `inputs`, `outputs`, `start_time`, `end_time`, `extra` metadata, and `parent_run_id`.

When executing a LangGraph agent, LangSmith automatically constructs a nested hierarchy:

```
Root Run: Graph Execution (run_type: "chain", name: "agent_recovery_graph")
 ├── Child Run: Node "agent_node" (run_type: "chain")
 │    └── Child Run: ChatModel (run_type: "llm", model: "claude-3-7-sonnet" / "gemini-2.5-pro")
 │         └── Prompts, system prompts, token usage, time-to-first-token
 ├── Child Run: Node "tool_executor" (run_type: "chain")
 │    └── Child Run: Tool "query_crm_customer" (run_type: "tool")
 │         └── Input: {"customer_id": "CUST-9012"}, Output: {"status": "ACTIVE"}
 └── Child Run: State Persistence (checkpoint write to SqliteSaver/PostgresSaver)
```

### 2.2 Native Environment Configuration
LangSmith requires **zero code modifications** to core application logic. It operates via standard environment variables:

```bash
# Enable LangSmith V2 Tracing
export LANGCHAIN_TRACING_V2=true

# LangSmith API Key (or Tenant Token)
export LANGCHAIN_API_KEY="lsv2_pt_..."

# Project Partitioning (isolates environments: dev, staging, prod)
export LANGCHAIN_PROJECT="telekom-enterprise-agent-prod"

# Endpoint (defaults to SaaS, or override for Self-Hosted Enterprise VPC)
export LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"

# Asynchronous, non-blocking dispatch
export LANGCHAIN_CALLBACKS_BACKGROUND=true
```

### 2.3 Key LangSmith Capabilities for Enterprise Agents
1. **Time-Travel & State Inspection**: When an agent encounters an unhandled exception or loops indefinitely, LangSmith allows engineers to inspect the exact state payload at any checkpoint node.
2. **Dataset Extraction from Production**: Any failed trace or high-value multi-turn conversation can be converted into a golden test dataset with a single click or API call (`client.create_dataset(...)`).
3. **Automated Evaluators**: Run LLM-as-a-judge (e.g. correctness, hallucination, toxicity) asynchronously over production traces without adding runtime latency.
4. **Prompt Versioning & Playgrounds**: Test updated system prompts directly against past trace inputs.

---

## 3. Capturing Agent Internals with Standard Logging

While LangSmith is purpose-built for LLM-Ops, enterprise security, compliance, and cloud platform teams require logs to flow into centralized logging systems (Datadog, Splunk, Elastic, AWS CloudWatch).

### 3.1 What Internals Must Be Logged?
A production-grade agent logger must capture:
1. **Correlation IDs**:
   - `thread_id`: The conversation / persistence thread ID used by LangGraph checkpointers.
   - `run_id`: The unique execution ID of the specific graph run.
   - `step_id` or `node_name`: The active graph node (`agent`, `tools`, `human_review`).
2. **State Transitions**:
   - Snapshot of state keys before and after node execution.
   - Delta of messages appended to `messages` state.
3. **Tool Invocations**:
   - Exact tool name, input arguments, execution duration, and tool exit status.
4. **Token Usage & Latency**:
   - `prompt_tokens`, `completion_tokens`, `total_tokens`.
   - `latency_ms` (time elapsed inside model API vs. local execution).
5. **Errors & Interventions**:
   - Stack traces, retry attempts, circuit breaker states, fallback activations.

### 3.2 PII Scrubbing and Data Protection
In regulated environments (telecommunications, banking, healthcare), raw prompts and tool outputs must not contain unmasked Personally Identifiable Information (PII), credentials, or customer secrets.

The dual-telemetry design includes a **Sanitization Filter** that redacts:
- Email addresses (`[EMAIL_REDACTED]`)
- Credit card / IBAN numbers (`[PAYMENT_REDACTED]`)
- Bearer tokens, passwords, and API keys (`[CREDENTIAL_REDACTED]`)
- Customer phone numbers (`[PHONE_REDACTED]`)

---

## 4. Architectural Comparison: Tracing vs. Logging

| Dimension | LangSmith Tracing | Structured Enterprise Logging |
| :--- | :--- | :--- |
| **Data Format** | OpenTelemetry-compatible Span Graphs (`RunTree`) | Newline-delimited JSON (NDJSON), ECS, or Bunyan |
| **Latency Impact** | Zero (asynchronous thread pool / micro-batching) | Sub-millisecond (buffered stdout/stderr write) |
| **Retention** | 14-400 days (based on LangSmith tier / retention rules) | Long-term cold storage (S3/GCS glacier, 1-7 years for regulatory compliance) |
| **Search Paradigm** | Semantic filters (`metadata["user_id"] == "X"`, tags, feedback scores) | Lucene / SQL / LogQL / KQL queries (`@timestamp`, `level:ERROR`, `thread_id`) |
| **Offline Operation** | Traces queued locally or dropped if network is unreachable | Always captured locally on disk or stdout even in air-gapped environments |

---

## 5. Implementation Blueprints

### 5.1 Python Architecture Pattern
- **Logger**: Standard `logging` configured with a custom `JSONFormatter`.
- **Callback Handler**: `StructuredLoggingCallbackHandler(BaseCallbackHandler)` attached to `config={"callbacks": [...]}`.
- **PII Scrubbing**: Regex-based redaction applied before logging inputs and outputs.
- **Graph State Interceptor**: Optional node wrapper logging graph state transitions.

### 5.2 TypeScript Architecture Pattern
- **Logger**: Strongly-typed structured logger emitting formatted JSON to `process.stdout`.
- **Callback Handler**: `StructuredLoggingCallbackHandler extends BaseCallbackHandler` passed in the `RunnableConfig`.
- **PII Scrubbing**: Key-based and regex-based redaction.
- **Graph State Interceptor**: State transition logger tracking node inputs and outputs.

---

## 6. Security & Air-Gapped Environments

For deployments where data must never leave a private network:
1. **LangSmith Self-Hosted**: Deploy LangSmith in Kubernetes or Docker Compose inside your VPC (`LANGCHAIN_ENDPOINT="https://langsmith.internal.myorg.com"`).
2. **Masking at Source**: Configure `LANGCHAIN_HIDE_INPUTS=true` and `LANGCHAIN_HIDE_OUTPUTS=true` to send only latency, metadata, and token counters to LangSmith while keeping all raw text exclusively in local structured logs.
3. **Pure In-Band Fallback**: If external tracing is completely disabled (`LANGCHAIN_TRACING_V2=false`), the application's `StructuredLoggingCallbackHandler` continues to capture 100% of the operational internals without code changes.

