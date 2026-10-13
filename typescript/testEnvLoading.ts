import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {
  findWorkspaceEnv,
  loadWorkspaceEnv,
  getConfiguredProviders,
  validateProviderKey,
} from "./src/langchain_suite/core/env.js";

test("findWorkspaceEnv locates an existing .env file", () => {
  const envPath = findWorkspaceEnv();
  assert.ok(envPath, "Should locate a .env file");
  assert.ok(fs.existsSync(envPath!), `Resolved path should exist: ${envPath}`);
  assert.ok(envPath!.endsWith(".env"));
});

test("loadWorkspaceEnv populates process.env and mirrors GEMINI_API_KEY / GOOGLE_API_KEY", () => {
  const loadedPath = loadWorkspaceEnv();
  assert.ok(loadedPath, "loadWorkspaceEnv should return the loaded .env path");

  // Check key aliasing
  if (process.env.GEMINI_API_KEY) {
    assert.equal(
      process.env.GOOGLE_API_KEY,
      process.env.GEMINI_API_KEY,
      "GOOGLE_API_KEY should be mirrored from GEMINI_API_KEY"
    );
  } else if (process.env.GOOGLE_API_KEY) {
    assert.equal(
      process.env.GEMINI_API_KEY,
      process.env.GOOGLE_API_KEY,
      "GEMINI_API_KEY should be mirrored from GOOGLE_API_KEY"
    );
  }
});

test("getConfiguredProviders returns dictionary of boolean flags", () => {
  const providers = getConfiguredProviders();
  assert.equal(typeof providers.openai, "boolean");
  assert.equal(typeof providers.anthropic, "boolean");
  assert.equal(typeof providers.gemini, "boolean");
  assert.equal(typeof providers.openrouter, "boolean");
});

test("validateProviderKey validates presence and reports missing keys with instructions", () => {
  // Mock should always succeed
  assert.doesNotThrow(() => validateProviderKey("mock"));

  // Unsupported provider should throw
  assert.throws(
    () => validateProviderKey("unknown_provider" as any),
    /Unsupported provider/
  );

  // Missing key for real provider should throw with actionable diagnostics
  const origAnthropic = process.env.ANTHROPIC_API_KEY;
  try {
    delete process.env.ANTHROPIC_API_KEY;
    assert.throws(
      () => validateProviderKey("anthropic"),
      /ANTHROPIC_API_KEY environment variable is missing/
    );
  } finally {
    if (origAnthropic) process.env.ANTHROPIC_API_KEY = origAnthropic;
  }
});
