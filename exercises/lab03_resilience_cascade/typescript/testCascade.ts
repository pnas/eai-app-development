import test from "node:test";
import assert from "node:assert/strict";
import {
  FallbackCascade,
  CircuitBreaker,
  CircuitState,
} from "./solution.js";

test("FallbackCascade uses primary provider when healthy", async () => {
  const p1 = {
    name: "claude-sonnet",
    caller: async () => "Sonnet Response",
  };
  const p2 = {
    name: "gpt-4o",
    caller: async () => "GPT-4o Response",
  };

  const cascade = new FallbackCascade([p1, p2]);
  const res = await cascade.execute("Hello");

  assert.equal(res.servedBy, "claude-sonnet");
  assert.equal(res.result, "Sonnet Response");
  assert.equal(res.cascadeDepth, 1);
});

test("FallbackCascade fails over to secondary on primary 529/500 error", async () => {
  const p1 = {
    name: "claude-sonnet",
    caller: async () => {
      const err: any = new Error("Anthropic Overloaded");
      err.status = 529;
      throw err;
    },
  };
  const p2 = {
    name: "gpt-4o",
    caller: async () => "GPT-4o Recovered",
  };

  const cascade = new FallbackCascade([p1, p2]);
  const res = await cascade.execute("Hello");

  assert.equal(res.servedBy, "gpt-4o");
  assert.equal(res.result, "GPT-4o Recovered");
  assert.equal(res.cascadeDepth, 2);
});

test("FallbackCascade bypasses primary when circuit is OPEN", async () => {
  let p1Calls = 0;
  const breaker = new CircuitBreaker(2);

  const p1 = {
    name: "claude-sonnet",
    caller: async () => {
      p1Calls++;
      const err: any = new Error("Service Unavailable");
      err.status = 503;
      throw err;
    },
    breaker,
  };
  const p2 = {
    name: "gpt-4o",
    caller: async () => "GPT-4o OK",
  };

  const cascade = new FallbackCascade([p1, p2]);

  // Trip the circuit with 2 failures
  await cascade.execute("Req 1");
  await cascade.execute("Req 2");
  assert.equal(breaker.state, CircuitState.OPEN);
  assert.equal(p1Calls, 2);

  // Third request must bypass p1 without invoking it
  const res = await cascade.execute("Req 3");
  assert.equal(res.servedBy, "gpt-4o");
  assert.ok(res.bypassedProviders.includes("claude-sonnet"));
  assert.equal(p1Calls, 2, "Primary caller should NOT have been invoked when circuit is OPEN");
});

test("FallbackCascade does not fallback on client 400 error", async () => {
  let p2Called = false;
  const p1 = {
    name: "claude-sonnet",
    caller: async () => {
      const err: any = new Error("Bad Request: Invalid JSON Schema");
      err.status = 400;
      throw err;
    },
  };
  const p2 = {
    name: "gpt-4o",
    caller: async () => {
      p2Called = true;
      return "Should not run";
    },
  };

  const cascade = new FallbackCascade([p1, p2]);

  await assert.rejects(
    async () => await cascade.execute("Bad prompt"),
    (err: any) => err.status === 400
  );

  assert.equal(p2Called, false, "Secondary must NOT be called on 400 error");
});

