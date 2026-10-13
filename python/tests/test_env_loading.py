"""Tests for workspace environment discovery, key aliasing, and provider validation."""

import os
import pytest
from fastapi.testclient import TestClient

from src.langchain_suite.core.env import (
    find_workspace_env,
    get_configured_providers,
    load_workspace_env,
    validate_provider_key,
)
from src.langchain_suite.frontend_agent.backend.server import app


def test_find_workspace_env():
    """Verify find_workspace_env locates python/.env or root .env."""
    env_path = find_workspace_env()
    assert env_path is not None
    assert env_path.name == ".env"
    assert env_path.exists()


def test_load_workspace_env_mirrors_gemini():
    """Verify GEMINI_API_KEY and GOOGLE_API_KEY are synchronized."""
    load_workspace_env()
    gemini_key = os.getenv("GEMINI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        assert google_key == gemini_key


def test_configured_providers_report():
    """Verify get_configured_providers returns boolean status map."""
    providers = get_configured_providers()
    assert "mock" in providers
    assert providers["mock"] is True
    assert "openai" in providers
    assert "anthropic" in providers
    assert "gemini" in providers
    # In this environment, python/.env is populated
    assert providers["anthropic"] is True
    assert providers["openai"] is True
    assert providers["gemini"] is True


def test_validate_provider_key():
    """Verify validate_provider_key accepts valid providers and rejects unknown."""
    # Mock always succeeds
    validate_provider_key("mock")

    # Anthropic should succeed since ANTHROPIC_API_KEY is present
    validate_provider_key("anthropic")

    # Invalid provider
    with pytest.raises(ValueError, match="Unsupported provider"):
        validate_provider_key("nonexistent_llm_provider")


def test_backend_health_reports_providers():
    """Verify FastAPI GET /health includes configured_providers dictionary."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured_providers" in data
    assert data["configured_providers"]["anthropic"] is True
    assert data["configured_providers"]["openai"] is True
    assert data["configured_providers"]["gemini"] is True


def test_anthropic_agent_initialization():
    """Verify that provider='anthropic' initializes without missing ANTHROPIC_API_KEY error."""
    from src.langchain_suite.frontend_agent.backend.server import get_cached_agent
    agent = get_cached_agent(provider="anthropic", model=None)
    assert agent is not None


def test_empty_env_var_overwritten_by_dotenv():
    """Verify that blank/empty environment variables do not shadow valid keys in .env."""
    original = os.environ.get("ANTHROPIC_API_KEY")
    try:
        # Simulate container or shell defining empty string
        os.environ["ANTHROPIC_API_KEY"] = "   "
        load_workspace_env()
        # Should be re-populated with the real key
        restored = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        assert len(restored) > 0
    finally:
        if original is not None:
            os.environ["ANTHROPIC_API_KEY"] = original


def test_package_resource_discovery():
    """Verify that package-closer .env exists and is discoverable."""
    from pathlib import Path
    import src.langchain_suite as pkg
    pkg_dir = Path(pkg.__file__).parent
    pkg_env = pkg_dir / ".env"
    assert pkg_env.is_file(), f"Expected package-closer .env at {pkg_env}"


