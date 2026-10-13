import test from "node:test";
import assert from "node:assert/strict";
import {
  runParadigm1,
  runParadigm2,
  runParadigm3,
  runParadigm4,
  runParadigm5,
  runParadigm6,
  runAll,
} from "./src/langchain_suite/cli.js";

test("TypeScript CLI: Paradigm 1 executes in mock mode", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm1("mock");
  });
});

test("TypeScript CLI: Paradigm 2 executes in mock mode", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm2("mock");
  });
});

test("TypeScript CLI: Paradigm 3 executes in mock mode", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm3("mock");
  });
});

test("TypeScript CLI: Paradigm 4 executes in mock mode", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm4("mock", 2);
  });
});

test("TypeScript CLI: Paradigm 5 executes fallback cascade and recovers", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm5(true);
  });
});

test("TypeScript CLI: Paradigm 6 executes cost router and gateway demo", async () => {
  await assert.doesNotReject(async () => {
    await runParadigm6(true);
  });
});

test("TypeScript CLI: runAll executes all 6 paradigms end-to-end", async () => {
  await assert.doesNotReject(async () => {
    await runAll("mock");
  });
});
