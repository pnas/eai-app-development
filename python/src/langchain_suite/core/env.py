"""Unified Environment Variable and API Key Loader for Python Services.

Provides resilient, multi-layer discovery of `.env` files across monorepo directories:
- Direct package resource loading (`importlib.resources` from `src.langchain_suite`)
- Immediate package proximity (`src/langchain_suite/.env`)
- Explicit workspace paths (`python/.env`)
- Upward ancestor directory traversal
- Bidirectional key aliasing (GEMINI_API_KEY <-> GOOGLE_API_KEY)
- Protection against empty-string environment variables shadowing `.env` values
- Safe provider validation and readiness status diagnostics
"""

from __future__ import annotations

import importlib.resources
import os
import shutil
from pathlib import Path
from typing import Dict, Optional
from dotenv import dotenv_values, load_dotenv

# Cached resolution state
_LOADED_ENV_PATH: Optional[Path] = None

# Known canonical workspace locations
_KNOWN_CANONICAL_PATHS = [
    Path(r"C:\Users\PantelisNasikas\workspace\genai_agents_api\telekom_courses\advanced_ai_integration\python\.env"),
]


def _sync_package_env(source_path: Path, target_path: Path) -> None:
    """Safely synchronizes the source .env file to the package resource location if newer or missing."""
    try:
        if source_path.is_file():
            if not target_path.exists() or source_path.stat().st_mtime > target_path.stat().st_mtime:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
    except Exception:
        pass


def find_workspace_env() -> Optional[Path]:
    """Discovers the active .env file across standard project locations."""
    # 1. Explicit override via environment variables
    for custom_var in ("APP_ENV_FILE", "DOTENV_PATH", "ENV_FILE"):
        custom_path = os.getenv(custom_var)
        if custom_path and Path(custom_path).is_file():
            return Path(custom_path).resolve()

    current = Path(__file__).resolve().parent

    # 2. Immediate proximity checks relative to this module
    package_suite_dir = current.parent  # src/langchain_suite
    package_env = package_suite_dir / ".env"

    # Auto-sync from python/.env to package .env if found
    for parent in [current] + list(current.parents):
        src_candidate = parent / "python" / ".env"
        if src_candidate.is_file():
            _sync_package_env(src_candidate, package_env)
            break

    proximity_candidates = [
        package_env,
        current / ".env",
        package_suite_dir.parent / ".env",  # src/.env
        package_suite_dir.parent.parent / ".env",  # python/.env
    ]
    for candidate in proximity_candidates:
        if candidate.is_file():
            return candidate.resolve()

    # 3. Python Package Resources (importlib.resources)
    for pkg in ("src.langchain_suite", "langchain_suite"):
        try:
            res = importlib.resources.files(pkg) / ".env"
            if res.is_file():
                try:
                    p = Path(str(res)).resolve()
                    if p.is_file():
                        return p
                except Exception:
                    pass
        except Exception:
            pass

    # 4. Known canonical paths on system
    for known in _KNOWN_CANONICAL_PATHS:
        if known.is_file():
            _sync_package_env(known, package_env)
            return known.resolve()

    # 5. Upward search from this file's location through all parent directories
    for parent in [current] + list(current.parents):
        candidates = [
            parent / "python" / ".env",
            parent / ".env",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

    # 6. Check current working directory
    cwd = Path.cwd().resolve()
    for candidate in [
        cwd / "python" / ".env",
        cwd / "src" / "langchain_suite" / ".env",
        cwd / ".env",
    ]:
        if candidate.is_file():
            return candidate.resolve()

    return None


def load_workspace_env(override: bool = False) -> Optional[Path]:
    """Loads environment variables into os.environ with resilient multi-layer fallback and aliasing.

    Ensures that empty string environment variables (e.g. from container definitions)
    do not mask valid non-empty values defined in the .env file.

    Args:
        override: If True, values from the .env file will overwrite existing non-empty variables.

    Returns:
        The Path to the loaded .env file, or None if no file was found.
    """
    global _LOADED_ENV_PATH

    env_path = find_workspace_env()
    if env_path and env_path.is_file():
        # Read explicit key-value pairs
        parsed_values = dotenv_values(dotenv_path=env_path)
        for k, v in parsed_values.items():
            if v is not None and str(v).strip():
                # Populate if missing, if override is requested, or if current env var is blank
                existing = os.getenv(k)
                if override or existing is None or not existing.strip():
                    os.environ[k] = str(v).strip()

        # Let load_dotenv handle any system-level parsing
        load_dotenv(dotenv_path=env_path, override=override)
        _LOADED_ENV_PATH = env_path
    else:
        load_dotenv(override=override)

    # Bidirectional Aliasing for Google Gemini API Keys
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if gemini_key and not google_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
    elif google_key and not gemini_key:
        os.environ["GEMINI_API_KEY"] = google_key

    return _LOADED_ENV_PATH


def get_loaded_env_path() -> Optional[Path]:
    """Returns the path of the successfully loaded .env file, if any."""
    return _LOADED_ENV_PATH


def get_configured_providers() -> Dict[str, bool]:
    """Returns a readiness map indicating which LLM providers have valid API keys set."""
    load_workspace_env()
    return {
        "mock": True,
        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "gemini": bool(
            os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        ),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
    }


def validate_provider_key(provider: str) -> None:
    """Validates that the necessary API key is configured for the requested provider.

    Raises:
        ValueError: If the required key is missing, with clear instructions on how to set it.
    """
    load_workspace_env()
    prov = (provider or "mock").strip().lower()

    if prov == "mock":
        return

    key_map = {
        "openai": ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        "open_ai": ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        "anthropic": ("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
        "claude": ("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY")),
        "gemini": ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "google": ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "google-genai": ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "openrouter": ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY")),
    }

    if prov not in key_map:
        raise ValueError(
            f"Unsupported provider '{provider}'. Choose from: 'mock', 'openai', 'anthropic', 'gemini'."
        )

    var_name, val = key_map[prov]
    if not val or not val.strip():
        loaded_from = f" (loaded from: {_LOADED_ENV_PATH})" if _LOADED_ENV_PATH else " (no .env found)"
        raise ValueError(
            f"{var_name} environment variable is missing for provider '{provider}'{loaded_from}. "
            f"Please define {var_name} in python/.env or export it in your shell environment."
        )


# Automatically load workspace env when this module is imported
load_workspace_env()
