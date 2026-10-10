import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { ChatAnthropic } from "@langchain/anthropic";
import pc from "picocolors";

const TELECOM_SOP_PREFIX = `
# TELECOMMUNICATIONS NETWORK STANDARD OPERATING PROCEDURES (TS-9021-V4)
This technical standard defines network fault remediation, optical line diagnostics,
and cell-tower handoff protocols for 5G NextGen Core networks.
SECTION 1: OPTICAL TIME-DOMAIN REFLECTOMETER (OTDR) DIAGNOSTICS
When an optical backhaul reports attenuation exceeding 0.35 dB/km on single-mode fiber (G.652),
the Network Operations Center (NOC) must initiate an automated OTDR trace.
Events with loss greater than 0.5 dB are flagged as severe mechanical splices or macrobends.
SECTION 2: CELL SITE GATEWAY (CSG) PROTOCOLS
All CSG routers running Segment Routing over IPv6 (SRv6) maintain bidirectional forwarding
detection (BFD) timers configured with 10ms intervals and multiplier 3.
Upon 3 consecutive dropped BFD packets, the node shifts traffic to the precomputed
Loop-Free Alternate (TI-LFA) backup path within 50ms.
`.repeat(8);

async function runPromptCacheDemo() {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    console.log(pc.yellow("Skipping prompt cache demo: ANTHROPIC_API_KEY not defined."));
    return;
  }

  const model = new ChatAnthropic({
    model: "claude-3-5-haiku-20241022",
    temperature: 0,
    apiKey,
  });

  const cachedSystemMessage = new SystemMessage({
    content: [
      {
        type: "text",
        text: TELECOM_SOP_PREFIX,
        // @ts-ignore - provider-specific field
        cache_control: { type: "ephemeral" },
      },
    ],
  });

  console.log(pc.yellow("\n=== Module 3 (TypeScript): Prompt Caching via LangChain ===\n"));

  console.log(pc.cyan("Turn 1: Cache Miss / Cold Creation..."));
  const res1 = await model.invoke([
    cachedSystemMessage,
    new HumanMessage("What is the BFD timer interval specified in Section 2?"),
  ]);

  console.log("Turn 1 Response:", res1.content);
  console.log("Turn 1 Usage:", res1.response_metadata?.usage ?? "N/A");

  console.log(pc.cyan("\nTurn 2: Cache Hit / Warm Read..."));
  const res2 = await model.invoke([
    cachedSystemMessage,
    new HumanMessage("What is the attenuation threshold in Section 1?"),
  ]);

  console.log("Turn 2 Response:", res2.content);
  console.log("Turn 2 Usage:", res2.response_metadata?.usage ?? "N/A");
}

if (process.argv[1]?.includes("promptCache")) {
  runPromptCacheDemo().catch(console.error);
}

