# TypeScript Examples: Advanced GenAI API Integration

Production TypeScript examples targeting Node.js 24+, leveraging official provider SDKs (`openai`, `@anthropic-ai/sdk`, `@google/genai`), and **Zod** for compile-time and runtime type safety.

---

## 🛠️ Setup

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your provider API keys
   ```

---

## 📂 Module Execution Commands

| Module | Topic | Run Command |
| :--- | :--- | :--- |
| **01** | Cross-Provider Chat Comparison | `npm run start:m01` |
| **01** | SSE Streaming & Token Extraction | `npm run start:m01:stream` |
| **01** | Wire Protocol Tool Calling | `npm run start:m01:tool` |
| **02** | OpenAI Strict Output (`zodResponseFormat`) | `npm run start:m02` |
| **02** | Anthropic Forced Tool Schema | `npm run start:m02:anthropic` |
| **02** | Self-Healing JSON Repair Loop | `npm run start:m02:repair` |
| **03** | Cache Invalidation Benchmark | `npm run start:m03` |
| **03** | Anthropic Ephemeral Breakpoints | `npm run start:m03:anthropic` |
| **04** | Batch State Machine & DLQ | `npm run start:m04` |
| **05** | Production Circuit Breaker | `npm run start:m05` |
| **05** | Multi-Provider Fallback Cascade | `npm run start:m05:fallback` |
| **06** | Interactive Cost & ROI Calculator | `npm run start:m06` |

