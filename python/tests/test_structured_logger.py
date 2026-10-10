"""Unit tests for Enterprise Structured Logging & PII Scrubbing."""

import json
import logging
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.outputs import LLMResult, Generation

from src.langchain_suite.core.structured_logger import (
    PIIScrubber,
    StructuredLoggingCallbackHandler,
    safe_json_default,
)


def test_pii_scrubber_redacts_sensitive_patterns():
    text = "Contact user at alice.smith@telekom.de or call +49 170 5551234 with api_key='secret123456'"
    scrubbed = PIIScrubber.scrub_text(text)
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "[REDACTED_CREDENTIAL]" in scrubbed
    assert "alice.smith@telekom.de" not in scrubbed
    assert "+49 170 5551234" not in scrubbed
    assert "secret123456" not in scrubbed


def test_pii_scrubber_handles_nested_data_and_messages():
    raw_data = {
        "user_email": "support@customer.com",
        "api_secret": "super-confidential-token-value",
        "nested": {
            "token": "bearer-token-12345",
            "message": "Call (555) 123-4567 urgently",
        },
    }
    scrubbed = PIIScrubber.scrub_data(raw_data)
    assert scrubbed["user_email"] == "[REDACTED_EMAIL]"
    assert scrubbed["api_secret"] == "[REDACTED_CREDENTIAL]"
    assert scrubbed["nested"]["token"] == "[REDACTED_CREDENTIAL]"
    assert "[REDACTED_PHONE]" in scrubbed["nested"]["message"]

    # Test LangChain Message scrubbing
    ai_msg = AIMessage(content="Customer phone is +1-800-555-0199")
    scrubbed_msg = PIIScrubber.scrub_data(ai_msg)
    assert scrubbed_msg["type"] == "ai"
    assert "[REDACTED_PHONE]" in scrubbed_msg["content"]


def test_callback_handler_records_chat_model_lifecycle():
    mock_logger = MagicMock(spec=logging.Logger)
    handler = StructuredLoggingCallbackHandler(logger=mock_logger, thread_id="test-thread-99")

    # 1. on_chat_model_start
    handler.on_chat_model_start(
        serialized={"name": "ChatOpenAI"},
        messages=[[HumanMessage(content="Hello AI")]],
        run_id="run-uuid-1",
        invocation_params={"model_name": "gpt-4o-mini"},
    )
    assert mock_logger.info.called
    first_call_extra = mock_logger.info.call_args[1]["extra"]
    assert first_call_extra["agent_event"] == "llm.start"
    assert first_call_extra["correlation"]["thread_id"] == "test-thread-99"
    assert first_call_extra["correlation"]["run_id"] == "run-uuid-1"

    # 2. on_llm_end
    response = LLMResult(
        generations=[[Generation(text="Hello subscriber")]],
        llm_output={"token_usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}},
    )
    handler.on_llm_end(response, run_id="run-uuid-1")
    second_call_extra = mock_logger.info.call_args[1]["extra"]
    assert second_call_extra["agent_event"] == "llm.end"
    assert second_call_extra["telemetry"]["tokens"]["total_tokens"] == 20
    assert "duration_ms" in second_call_extra["telemetry"]


def test_callback_handler_tool_invocation_and_error():
    mock_logger = MagicMock(spec=logging.Logger)
    handler = StructuredLoggingCallbackHandler(logger=mock_logger, thread_id="test-thread-99")

    # on_tool_start
    handler.on_tool_start(
        serialized={"name": "lookup_customer"},
        input_str="user=john.doe@telekom.com",
        run_id="tool-run-1",
    )
    assert mock_logger.info.called
    start_extra = mock_logger.info.call_args[1]["extra"]
    assert start_extra["agent_event"] == "tool.start"
    assert "[REDACTED_EMAIL]" in start_extra["payload"]["input"]

    # on_tool_error
    handler.on_tool_error(
        error=ValueError("Connection timed out to CRM"),
        run_id="tool-run-1",
    )
    assert mock_logger.error.called
    err_extra = mock_logger.error.call_args[1]["extra"]
    assert err_extra["agent_event"] == "tool.error"
    assert err_extra["telemetry"]["error_type"] == "ValueError"

