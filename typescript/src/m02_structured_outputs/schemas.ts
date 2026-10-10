import { z } from "zod";

export const RiskLevelSchema = z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]);
export type RiskLevel = z.infer<typeof RiskLevelSchema>;

export const ComponentRiskSchema = z.object({
  componentName: z.string().describe("Name of the affected service or subsystem."),
  riskLevel: RiskLevelSchema.describe("Categorical risk rating."),
  description: z.string().describe("Clear explanation of the failure mode or vulnerability."),
  mitigationStrategy: z.string().describe("Concrete engineering fix."),
}).strict(); // .strict() ensures additionalProperties: false for OpenAI strict mode!

export type ComponentRisk = z.infer<typeof ComponentRiskSchema>;

export const SystemArchitectureSpecSchema = z.object({
  systemName: z.string().describe("Official name of the architecture or service."),
  estimatedMonthlyTcoUsd: z.number().describe("Total cost of ownership estimation in USD."),
  scalabilityRating1To10: z.number().min(1).max(10).describe("Scale of 1-10."),
  risks: z.array(ComponentRiskSchema).describe("Identified architectural risks."),
  recommendedPatterns: z.array(z.string()).describe("Resilience and architecture patterns to adopt."),
}).strict();

export type SystemArchitectureSpec = z.infer<typeof SystemArchitectureSpecSchema>;

