import test from "node:test";
import assert from "node:assert/strict";
import {
  TokenBucket,
  calculateDecorrelatedJitter,
  executeWithResilience,
} from "./solution.js";

test("TokenBucket allows immediate burst within capacity", async () => {
  const bucket = new TokenBucket(5.0, 1.0);
  const start = Date.now();
  const waited = await bucket.acquire(3.0);
  const elapsed = Date.now() - start;

  assert.equal(waited, 0);
  assert.ok(elapsed < 50);
  assert.ok(bucket.getAvailableTokens() <= 2.1);
});

test("TokenBucket throttles when capacity is exhausted", async () => {
  const bucket = new TokenBucket(2.0, 10.0); // 10 tokens/sec
  await bucket.acquire(2.0); // Drain completely

  const start = Date.now();
  const waited = await bucket.acquire(2.0); // Wait for 2 tokens = ~200ms
  const elapsed = Date.now() - start;

  assert.ok(elapsed >= 180, `Expected elapsed >= 180ms, got ${elapsed}ms`);
  assert.ok(waited >= 0.18, `Expected waited >= 0.18s, got ${waited}s`);
});

test("Decorrelated jitter stays within bounds", () => {
  const base = 10;
  const max = 200;
  let prev = 20;

  for (let i = 0; i < 100; i++) {
    const jittered = calculateDecorrelatedJitter(base, max, prev);
    assert.ok(jittered >= base, `Jittered ${jittered} < base ${base}`);
    assert.ok(jittered <= max, `Jittered ${jittered} > max ${max}`);
    prev = jittered;
  }
});

test("executeWithResilience retries on 429 and returns successful result", async () => {
  const bucket = new TokenBucket(10.0, 100.0);
  let attempts = 0;

  const mockApi = async () => {
    attempts++;
    if (attempts <= 2) {
      const err: any = new Error("Rate limit exceeded");
      err.status = 429;
      throw err;
    }
    return { ok: true, attempts };
  };

  const res = await executeWithResilience(
    mockApi,
    bucket,
    1.0,
    3,
    10,
    100
  );

  assert.equal(res.ok, true);
  assert.equal(res.attempts, 3);
});

