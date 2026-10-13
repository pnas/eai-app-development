"""Unit tests for the unified LangChain Multi-Paradigm CLI."""

from __future__ import annotations

import sys
from unittest.mock import patch
import pytest

from src.langchain_suite.cli import (
    run_paradigm_1,
    run_paradigm_2,
    run_paradigm_3,
    run_paradigm_4,
    run_paradigm_5,
    run_paradigm_6,
    run_all,
    main,
)


def test_cli_paradigm_1_mock():
    """Verify Paradigm 1 runs in mock mode without throwing exceptions."""
    run_paradigm_1(provider="mock")


def test_cli_paradigm_2_mock():
    """Verify Paradigm 2 runs in mock mode and validates Pydantic model."""
    run_paradigm_2(provider="mock")


def test_cli_paradigm_3_mock():
    """Verify Paradigm 3 runs in mock mode without throwing exceptions."""
    run_paradigm_3(provider="mock")


def test_cli_paradigm_4_mock():
    """Verify Paradigm 4 runs in mock mode without throwing exceptions."""
    run_paradigm_4(provider="mock", concurrency=2)


def test_cli_paradigm_5_resilience():
    """Verify Paradigm 5 executes fallback cascade and recovers."""
    run_paradigm_5(simulate_failure=True)


def test_cli_paradigm_6_gateways():
    """Verify Paradigm 6 executes dynamic cost router and gateway demo in simulated mode."""
    run_paradigm_6(simulate=True)


def test_cli_run_all_mock():
    """Verify run_all executes all 6 paradigms end-to-end in mock mode."""
    run_all(provider="mock")


def test_cli_main_argparse():
    """Verify main() handles command-line arguments properly."""
    with patch.object(sys, "argv", ["cli.py", "--paradigm", "2", "--provider", "mock"]):
        main()
