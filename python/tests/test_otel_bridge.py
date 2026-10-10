"""Unit tests for OpenTelemetry GenAI Semantic Conventions Bridge."""

import uuid
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from src.langchain_suite.core.otel_bridge import (
    OpenTelemetryGenAICallbackHandler,
    OpenTelemetrySpan,
    generate_span_id,
    generate_trace_id,
)


def test_trace_and_span_id_generation():
    trace_id = generate_trace_id()
    span_id = generate_span_id()

    assert len(trace_id) == 32
    assert len(span_id) == 16
    int(trace_id, 16)  # must be valid hex
    int(span_id, 16)   # must be valid hex


def test_span_lifecycle_and_duration():
    span = OpenTelemetrySpan(
        name="test.span",
        trace_id=generate_trace_id(),
        span_id=generate_span_id(),
    )
    assert span.status_code == "UNSET"
    assert span.end_time_ns is None

    span.finish(status_code="OK")
    assert span.status_code == "OK"
    assert span.end_time_ns is not None
    assert span.duration_ms >= 0


def test_otel_handler_chat_and_token_metrics():
    exported_spans = []
    handler = OpenTelemetryGenAICallbackHandler(
        service_name="telekom-agent-test",
        thread_id="thread-test-123",
        scrub_pii=True,
        span_exporter=lambda s: exported_spans.append(s),
    )

    run_id = uuid.uuid4()
    messages = [[HumanMessage(content="Reach me at john.doe@example.com")]]

    handler.on_chat_model_start(
        serialized={"kwargs": {"model": "gpt-4o"}},
        messages=messages,
        run_id=run_id,
        metadata={"model_name": "gpt-4o"},
    )

    # Simulate LLM end with token metrics
    llm_result = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="Hello John!"))]],
        llm_output={
            "token_usage": {
                "prompt_tokens": 15,
                "completion_tokens": 8,
                "total_tokens": 23,
            }
        },
    )
    handler.on_llm_end(llm_result, run_id=run_id)

    assert len(exported_spans) == 1
    span = exported_spans[0]

    assert span.name == "gen_ai.chat gpt-4o"
    assert span.attributes["gen_ai.system"] == "openai"
    assert span.attributes["gen_ai.request.model"] == "gpt-4o"
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.usage.prompt_tokens"] == 15
    assert span.attributes["gen_ai.usage.completion_tokens"] == 8
    assert span.attributes["gen_ai.usage.total_tokens"] == 23
    assert span.attributes["session.id"] == "thread-test-123"
    # PII scrubbing check
    assert "[REDACTED_EMAIL]" in span.attributes["gen_ai.prompt"]
    assert "john.doe@example.com" not in span.attributes["gen_ai.prompt"]


def test_otel_handler_tool_execution_and_parent_child():
    handler = OpenTelemetryGenAICallbackHandler(service_name="telekom-agent-test")

    chain_run_id = uuid.uuid4()
    handler.on_chain_start(
        serialized={"name": "AgentExecution"},
        inputs={"input": "test"},
        run_id=chain_run_id,
    )

    tool_run_id = uuid.uuid4()
    handler.on_tool_start(
        serialized={"name": "database_lookup"},
        input_str="customer_id=12345",
        run_id=tool_run_id,
    )

    handler.on_tool_end("record_found=True", run_id=tool_run_id)
    handler.on_chain_end({"output": "done"}, run_id=chain_run_id)

    assert len(handler.completed_spans) == 2
    tool_span = handler.completed_spans[0]
    chain_span = handler.completed_spans[1]

    assert tool_span.name == "gen_ai.tool database_lookup"
    assert tool_span.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool_span.parent_span_id == chain_span.span_id

    # Test OTLP export format
    otlp = handler.export_otlp_payload()
    assert "resourceSpans" in otlp
    assert otlp["resourceSpans"][0]["resource"]["attributes"][0]["key"] == "service.name"
    assert len(otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 2


def test_otel_handler_error_recording():
    handler = OpenTelemetryGenAICallbackHandler(service_name="telekom-agent-test")
    run_id = uuid.uuid4()

    handler.on_chat_model_start(
        serialized={"kwargs": {"model": "claude-3-5-sonnet"}},
        messages=[[HumanMessage(content="Query")]],
        run_id=run_id,
        metadata={"model_name": "claude-3-5-sonnet"},
    )

    handler.on_llm_error(RuntimeError("API 503 Overloaded"), run_id=run_id)

    assert len(handler.completed_spans) == 1
    span = handler.completed_spans[0]
    assert span.status_code == "ERROR"
    assert "API 503 Overloaded" in str(span.status_message)
    assert len(span.events) == 1
    assert span.events[0]["name"] == "exception"

