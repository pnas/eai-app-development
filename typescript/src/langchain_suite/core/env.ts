/**
 * Unified Environment Variable and API Key Loader for TypeScript Services.
 *
 * Provides resilient, multi-layer discovery of `.env` files across monorepo directories,
 * ensures bidirectional key aliasing (GEMINI_API_KEY <-> GOOGLE_API_KEY),
 * and provides provider validation and readiness status diagnostics.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

let loadedEnvPath: string | null = null;

/**
 * Discovers the active .env file across standard project locations.
 */
export function findWorkspaceEnv(): string | null {
  // 1. Explicit override via environment variables
  for (const customVar of ["DOTENV_PATH", "ENV_FILE"]) {
    const customPath = process.env[customVar];
    if (customPath && fs.existsSync(customPath) && fs.statSync(customPath).isFile()) {
      return path.resolve(customPath);
    }
  }

  // 2. Search upward from this file's location
  let currentDir = "";
  try {
    currentDir = path.dirname(fileURLToPath(import.meta.url));
  } catch {
    currentDir = process.cwd();
  }

  let dir = currentDir;
  for (let i = 0; i < 6; i++) {
    const candidates = [
      path.join(dir, "python", ".env"),
      path.join(dir, ".env"),
    ];

    for (const candidate of candidates) {
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
        return path.resolve(candidate);
      }
    }

    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  // 3. Check current working directory
  const cwd = process.cwd();
  const cwdCandidates = [
    path.join(cwd, "python", ".env"),
    path.join(cwd, ".env"),
  ];
  for (const candidate of cwdCandidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return path.resolve(candidate);
    }
  }

  return null;
}

/**
 * Loads environment variables with resilient discovery and key aliasing.
 */
export function loadWorkspaceEnv(force: boolean = false): string | null {
  if (loadedEnvPath !== null && !force) {
    return loadedEnvPath;
  }

  const envPath = findWorkspaceEnv();

  if (envPath) {
    dotenv.config({ path: envPath, override: force });
    loadedEnvPath = envPath;
  } else {
    dotenv.config({ override: force });
  }

  // Bidirectional Aliasing for Google Gemini API Keys
  const geminiKey = process.env.GEMINI_API_KEY;
  const googleKey = process.env.GOOGLE_API_KEY;
  if (geminiKey && !googleKey) {
    process.env.GOOGLE_API_KEY = geminiKey;
  } else if (googleKey && !geminiKey) {
    process.env.GEMINI_API_KEY = googleKey;
  }

  return loadedEnvPath;
}

/**
 * Returns the path of the successfully loaded .env file, if any.
 */
export function getLoadedEnvPath(): string | null {
  return loadedEnvPath;
}

/**
 * Returns a readiness map indicating which LLM providers have valid API keys set.
 */
export function getConfiguredProviders(): Record<string, boolean> {
  loadWorkspaceEnv();
  return {
    mock: true,
    openai: Boolean(process.env.OPENAI_API_KEY && process.env.OPENAI_API_KEY.trim()),
    anthropic: Boolean(process.env.ANTHROPIC_API_KEY && process.env.ANTHROPIC_API_KEY.trim()),
    gemini: Boolean(
      (process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY.trim()) ||
      (process.env.GOOGLE_API_KEY && process.env.GOOGLE_API_KEY.trim())
    ),
    openrouter: Boolean(process.env.OPENROUTER_API_KEY && process.env.OPENROUTER_API_KEY.trim()),
  };
}

/**
 * Validates that the necessary API key is configured for the requested provider.
 * Throws an Error with actionable diagnostics if missing.
 */
export function validateProviderKey(provider: string = "mock"): void {
  loadWorkspaceEnv();
  const prov = (provider || "mock").trim().toLowerCase();

  if (prov === "mock") return;

  const keyMap: Record<string, { varName: string; value: string | undefined }> = {
    openai: { varName: "OPENAI_API_KEY", value: process.env.OPENAI_API_KEY },
    open_ai: { varName: "OPENAI_API_KEY", value: process.env.OPENAI_API_KEY },
    anthropic: { varName: "ANTHROPIC_API_KEY", value: process.env.ANTHROPIC_API_KEY },
    claude: { varName: "ANTHROPIC_API_KEY", value: process.env.ANTHROPIC_API_KEY },
    gemini: {
      varName: "GEMINI_API_KEY",
      value: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY,
    },
    google: {
      varName: "GEMINI_API_KEY",
      value: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY,
    },
    "google-genai": {
      varName: "GEMINI_API_KEY",
      value: process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY,
    },
    openrouter: { varName: "OPENROUTER_API_KEY", value: process.env.OPENROUTER_API_KEY },
  };

  const config = keyMap[prov];
  if (!config) {
    throw new Error(
      `Unsupported provider '${provider}'. Choose from: 'mock', 'openai', 'anthropic', 'gemini'.`
    );
  }

  if (!config.value || !config.value.trim()) {
    const loadedFrom = loadedEnvPath ? ` (loaded from: ${loadedEnvPath})` : " (no .env found)";
    throw new Error(
      `${config.varName} environment variable is missing for provider '${provider}'${loadedFrom}. ` +
      `Please define ${config.varName} in python/.env or export it in your shell environment.`
    );
  }
}

// Automatically load workspace env when imported
loadWorkspaceEnv();
