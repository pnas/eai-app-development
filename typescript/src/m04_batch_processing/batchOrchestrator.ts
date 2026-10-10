import pc from "picocolors";

export enum BatchState {
  PENDING = "PENDING",
  SUBMITTED = "SUBMITTED",
  POLLING = "POLLING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  PARTIAL_SUCCESS = "PARTIAL_SUCCESS",
}

export interface BatchItem {
  customId: string;
  prompt: string;
  responseText?: string;
  statusCode?: number;
  errorMessage?: string;
}

export class BatchOrchestrator {
  public jobId: string;
  public state: BatchState = BatchState.PENDING;
  public items: Map<string, BatchItem> = new Map();
  public deadLetterQueue: BatchItem[] = [];

  constructor(jobId: string) {
    this.jobId = jobId;
  }

  addItem(customId: string, prompt: string) {
    this.items.set(customId, { customId, prompt });
  }

  recordSuccess(customId: string, statusCode: number, responseText: string) {
    const item = this.items.get(customId);
    if (item) {
      item.statusCode = statusCode;
      item.responseText = responseText;
    }
  }

  recordFailure(customId: string, statusCode: number, errorMessage: string) {
    const item = this.items.get(customId);
    if (item) {
      item.statusCode = statusCode;
      item.errorMessage = errorMessage;
      this.deadLetterQueue.push(item);
    }
  }

  finalizeState() {
    this.state = this.deadLetterQueue.length > 0 ? BatchState.PARTIAL_SUCCESS : BatchState.COMPLETED;
  }
}

async function main() {
  console.log(pc.bold("\n=== Enterprise Batch Orchestrator Simulation (TypeScript) ===\n"));

  const orchestrator = new BatchOrchestrator("ts_batch_job_prod_4091");
  orchestrator.addItem("tx-001", "Summarize Q1 network throughput metrics.");
  orchestrator.addItem("tx-002", "Extract entity relationships from billing contract.");
  orchestrator.addItem("tx-003", "Analyze security log for SQL injection signatures.");

  orchestrator.state = BatchState.SUBMITTED;
  console.log(pc.cyan(`Job ${orchestrator.jobId} submitted with ${orchestrator.items.size} tasks.`));

  // Simulate completion with 1 failure quarantined
  orchestrator.recordSuccess("tx-001", 200, "Q1 network throughput averaged 14.2 Gbps with 99.99% uptime.");
  orchestrator.recordSuccess("tx-002", 200, "Extracted 4 counterparties and 3 recurring payment obligations.");
  orchestrator.recordFailure("tx-003", 400, "Content filter triggered: potential exploit payload detected in input.");
  orchestrator.finalizeState();

  console.log(pc.bold(`\nFinal Job Status: `) + pc.magenta(orchestrator.state));

  for (const [id, item] of orchestrator.items.entries()) {
    if (item.errorMessage) {
      console.log(pc.red(`  [FAILED] ${id} (HTTP ${item.statusCode}): ${item.errorMessage}`));
    } else {
      console.log(pc.green(`  [OK] ${id} (HTTP ${item.statusCode}): ${item.responseText?.slice(0, 50)}...`));
    }
  }

  if (orchestrator.deadLetterQueue.length > 0) {
    console.log(pc.yellow(`\n[DLQ ALERT] Quarantined ${orchestrator.deadLetterQueue.length} item(s) to Dead-Letter Queue:`));
    orchestrator.deadLetterQueue.forEach((d) => {
      console.log(`  - Task ${d.customId} failed with code ${d.statusCode}: ${d.errorMessage}`);
    });
  }
}

main().catch(console.error);

