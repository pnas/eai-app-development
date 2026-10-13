import pc from "picocolors";
import { getAnthropicClient, getOpenAIClient, getGeminiClient } from "../m01_paradigms/clientFactory.js";

export enum BreakerState {
  CLOSED = "CLOSED",
  OPEN = "OPEN",
  HALF_OPEN = "HALF_OPEN",
}

export class CircuitBreakerOpenException extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CircuitBreakerOpenException";
  }
}

export class CircuitBreaker {
  public name: string;
  public failureThreshold: number;
  public recoveryTimeoutMs: number;

  public state: BreakerState = BreakerState.CLOSED;
  public failureCount: number = 0;
  public lastStateChange: number = Date.now();

  constructor(name: string, failureThreshold: number = 3, recoveryTimeoutMs: number = 5000) {
    this.name = name;
    this.failureThreshold = failureThreshold;
    this.recoveryTimeoutMs = recoveryTimeoutMs;
  }

  beforeCall() {
    const now = Date.now();
    if (this.state === BreakerState.OPEN) {
      const elapsed = now - this.lastStateChange;
      if (elapsed >= this.recoveryTimeoutMs) {
        this.state = BreakerState.HALF_OPEN;
        this.lastStateChange = now;
        console.log(pc.yellow(`[Breaker: ${this.name}] Transitioning to HALF_OPEN (Allowing single probe request)`));
      } else {
        const remainingSec = ((this.recoveryTimeoutMs - elapsed) / 1000).toFixed(1);
        throw new CircuitBreakerOpenException(
          `Circuit breaker '${this.name}' is OPEN. Fast-failing request (cool-off: ${remainingSec}s remaining).`
        );
      }
    }
  }

  recordSuccess() {
    if (this.state !== BreakerState.CLOSED) {
      console.log(pc.green(`[Breaker: ${this.name}] Probe succeeded! Resetting to CLOSED state.`));
    }
    this.state = BreakerState.CLOSED;
    this.failureCount = 0;
  }

  recordFailure(error: any) {
    this.failureCount++;
    console.log(pc.yellow(`[Breaker: ${this.name}] Failure recorded (${this.failureCount}/${this.failureThreshold}): ${error?.message || error}`));

    if (this.failureCount >= this.failureThreshold) {
      this.state = BreakerState.OPEN;
      this.lastStateChange = Date.now();
      console.log(pc.red(`[Breaker: ${this.name}] Failure threshold exceeded! Circuit breaker TRIPPED to OPEN.`));
    }
  }

  /**
   * Executes an asynchronous operation through the circuit breaker lifecycle:
   * 1. Checks beforeCall() -> throws CircuitBreakerOpenException if OPEN.
   * 2. Executes fn().
   * 3. On success -> calls recordSuccess().
   * 4. On error -> calls recordFailure(err) and rethrows.
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    this.beforeCall();
    try {
      const result = await fn();
      this.recordSuccess();
      return result;
    } catch (err: any) {
      this.recordFailure(err);
      throw err;
    }
  }
}

// ---------------------------------------------------------
// Live Model Callers (Anthropic, OpenAI, Google Gemini)
// ---------------------------------------------------------

export async function callAnthropicModel(prompt: string): Promise<string> {
  if (!process.env.ANTHROPIC_API_KEY) {
    return `[Mock Anthropic Claude] Handled query: "${prompt}". Status: Healthy.`;
  }
  const client = getAnthropicClient();
  try {
    const res = await client.messages.create({
      model: "claude-haiku-5-5",
      max_tokens: 60,
      messages: [{ role: "user", content: prompt }],
    });
    const block = res.content.find((b) => b.type === "text") as any;
    return block?.text ?? "";
  } catch {
    const res = await client.messages.create({
      model: "claude-3-5-haiku-20241022",
      max_tokens: 60,
      messages: [{ role: "user", content: prompt }],
    });
    const block = res.content.find((b) => b.type === "text") as any;
    return block?.text ?? "";
  }
}

export async function callOpenAIModel(prompt: string): Promise<string> {
  if (!process.env.OPENAI_API_KEY) {
    return `[Mock OpenAI GPT] Handled query: "${prompt}". Status: Healthy.`;
  }
  const client = getOpenAIClient();
  try {
    const res = await client.chat.completions.create({
      model: "gpt-4.1-mini",
      max_tokens: 60,
      messages: [{ role: "user", content: prompt }],
    });
    return res.choices[0]?.message?.content ?? "";
  } catch {
    const res = await client.chat.completions.create({
      model: "gpt-4o-mini",
      max_tokens: 60,
      messages: [{ role: "user", content: prompt }],
    });
    return res.choices[0]?.message?.content ?? "";
  }
}

export async function callGeminiModel(prompt: string): Promise<string> {
  if (!process.env.GEMINI_API_KEY && !process.env.GOOGLE_API_KEY) {
    return `[Mock Google Gemini] Handled query: "${prompt}". Status: Healthy.`;
  }
  const client = getGeminiClient();
  try {
    const res = await client.models.generateContent({
      model: "gemini-3.8-flash",
      contents: prompt,
    });
    return res.text ?? "";
  } catch {
    const res = await client.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
    });
    return res.text ?? "";
  }
}

// ---------------------------------------------------------
// Demonstration Workflow
// ---------------------------------------------------------

async function main() {
  console.log(pc.bold("\n=== Production Circuit Breaker with Frontier Models (TypeScript) ===\n"));

  const anthropicBreaker = new CircuitBreaker("Anthropic_Claude", 3, 2500);
  const openAiBreaker = new CircuitBreaker("OpenAI_GPT", 3, 2500);
  const geminiBreaker = new CircuitBreaker("Google_Gemini", 3, 2500);

  // Phase 1: Real Model Invocations via Circuit Breakers
  console.log(pc.cyan("Phase 1: Executing Live Model Calls Protected by Circuit Breakers (CLOSED state)..."));

  const testPrompt = "In 10 words or less, what is the role of 5G Standalone core?";

  try {
    const resAnthropic = await anthropicBreaker.execute(() => callAnthropicModel(testPrompt));
    console.log(pc.green(`✔ Anthropic Breaker [${anthropicBreaker.state}]: ${resAnthropic.trim()}`));
  } catch (err: any) {
    console.log(pc.yellow(`Anthropic call note: ${err.message}`));
  }

  try {
    const resOpenAI = await openAiBreaker.execute(() => callOpenAIModel(testPrompt));
    console.log(pc.green(`✔ OpenAI Breaker [${openAiBreaker.state}]: ${resOpenAI.trim()}`));
  } catch (err: any) {
    console.log(pc.yellow(`OpenAI call note: ${err.message}`));
  }

  try {
    const resGemini = await geminiBreaker.execute(() => callGeminiModel(testPrompt));
    console.log(pc.green(`✔ Gemini Breaker [${geminiBreaker.state}]: ${resGemini.trim()}`));
  } catch (err: any) {
    console.log(pc.yellow(`Gemini call note: ${err.message}`));
  }

  // Phase 2: Fault Injection & Trip Anthropic Breaker to OPEN
  console.log(pc.cyan("\nPhase 2: Inducing Consecutive 529/429 Outages on Anthropic to Trigger Circuit Breaker..."));
  for (let i = 1; i <= 3; i++) {
    try {
      await anthropicBreaker.execute(async () => {
        throw new Error(`HTTP 529 Overloaded: Claude infrastructure capacity exhausted (attempt ${i})`);
      });
    } catch {
      // Expected failure
    }
  }

  // Phase 3: Fast-Fail Verification (0ms overhead)
  console.log(pc.cyan("\nPhase 3: Fast-Fail Verification when Circuit is OPEN:"));
  const fastFailStart = performance.now();
  try {
    await anthropicBreaker.execute(() => callAnthropicModel("Test prompt during outage"));
  } catch (err: any) {
    const elapsedMs = (performance.now() - fastFailStart).toFixed(2);
    console.log(pc.red(`✔ FAST-FAIL CAUGHT in ${elapsedMs}ms (0 network calls made): ${err.message}`));
  }

  // Phase 4: Cool-off, Transition to HALF_OPEN & Real Model Probe Recovery
  console.log(pc.cyan("\nPhase 4: Waiting for cool-off timeout (2.6s) to allow HALF_OPEN probe..."));
  await new Promise((r) => setTimeout(r, 2600));

  try {
    console.log(pc.yellow("Sending probe request to real Anthropic model to test recovery..."));
    const probeRes = await anthropicBreaker.execute(() => callAnthropicModel("Ping recovery test"));
    console.log(pc.green(`✔ Probe succeeded! Response: ${probeRes.trim()}`));
    console.log(pc.green(`✔ Breaker state successfully recovered to: ${anthropicBreaker.state}`));
  } catch (err: any) {
    console.log(pc.red(`Probe failed: ${err.message}`));
  }

  // Phase 5: Resilient Router Demonstration
  console.log(pc.cyan("\nPhase 5: Resilient Router cascading across Breaker-Protected Models:"));
  // Intentionally trip Anthropic again
  for (let i = 0; i < 3; i++) {
    anthropicBreaker.recordFailure(new Error("Simulated transient downtime"));
  }

  const providers = [
    { name: "Anthropic", breaker: anthropicBreaker, caller: () => callAnthropicModel("What is eNodeB?") },
    { name: "OpenAI", breaker: openAiBreaker, caller: () => callOpenAIModel("What is eNodeB?") },
    { name: "Gemini", breaker: geminiBreaker, caller: () => callGeminiModel("What is eNodeB?") },
  ];

  let routedResult: string | null = null;
  let usedProvider: string | null = null;

  for (const p of providers) {
    try {
      console.log(pc.gray(`Checking ${p.name} circuit (state: ${p.breaker.state})...`));
      routedResult = await p.breaker.execute(p.caller);
      usedProvider = p.name;
      break;
    } catch (err: any) {
      if (err instanceof CircuitBreakerOpenException) {
        console.log(pc.yellow(`[ROUTER] ${p.name} circuit is OPEN. Fast-failing to next healthy provider.`));
      } else {
        console.log(pc.red(`[ROUTER] ${p.name} failed during call: ${err.message}`));
      }
    }
  }

  console.log(pc.green(`\n✔ Resilient Routing Successful! Answer served by healthy provider [${usedProvider}]:\n${routedResult?.trim()}\n`));
}

if (process.argv[1]?.includes("circuitBreaker")) {
  main().catch(console.error);
}
