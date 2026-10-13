/**
 * Frontend Agent Studio - Browser Application Logic
 *
 * Implements SSE stream parsing, dynamic tool call rendering,
 * and switching between Pattern A (In-Process) and Pattern B (Decoupled Microservice).
 */

const state = {
  pattern: "in-process", // "in-process" | "remote"
  provider: "mock",
  remoteUrl: "http://localhost:4000/agent/chat/stream",
  threadId: `thread-ts-${Math.random().toString(36).substring(2, 9)}`,
  history: [],
  isStreaming: false,
};

// DOM References
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const providerSelect = document.getElementById("providerSelect");
const remoteBackendSection = document.getElementById("remoteBackendSection");
const remoteUrlInput = document.getElementById("remoteUrlInput");
const activePatternTitle = document.getElementById("activePatternTitle");
const activePatternDesc = document.getElementById("activePatternDesc");
const activeProviderBadge = document.getElementById("activeProviderBadge");
const activeThreadBadge = document.getElementById("activeThreadBadge");
const serviceStatus = document.getElementById("serviceStatus");
const statusText = document.getElementById("statusText");
const toolList = document.getElementById("toolList");
const toolCount = document.getElementById("toolCount");
const btnRefreshTools = document.getElementById("btnRefreshTools");

// Pattern Radios
const patternACard = document.getElementById("patternA-card");
const patternBCard = document.getElementById("patternB-card");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  activeThreadBadge.textContent = `Thread: #${state.threadId}`;
  setupEventListeners();
  fetchTools();
});

function setupEventListeners() {
  // Pattern switching
  document.querySelectorAll('input[name="pattern"]').forEach((radio) => {
    radio.addEventListener("change", (e) => {
      state.pattern = e.target.value;
      if (state.pattern === "in-process") {
        patternACard.classList.add("active");
        patternBCard.classList.remove("active");
        remoteBackendSection.style.display = "none";
        activePatternTitle.textContent = "Pattern A: In-Process Monolith";
        activePatternDesc.textContent =
          "Agent runs within the Web Server process. Direct SSE pipeline with minimum latency.";
      } else {
        patternBCard.classList.add("active");
        patternACard.classList.remove("active");
        remoteBackendSection.style.display = "block";
        activePatternTitle.textContent = "Pattern B: Decoupled Microservice";
        activePatternDesc.textContent =
          "Agent runs in an independent SSE microservice process. Decoupled compute and isolated scaling.";
      }
    });
  });

  // Provider selector
  providerSelect.addEventListener("change", (e) => {
    state.provider = e.target.value;
    activeProviderBadge.textContent = `Provider: ${state.provider}`;
  });

  // Remote URL input
  remoteUrlInput.addEventListener("input", (e) => {
    state.remoteUrl = e.target.value.trim();
  });

  // Auto-resize textarea
  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
  });

  // Keyboard submit on Enter (without shift)
  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Form submit
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const prompt = messageInput.value.trim();
    if (!prompt || state.isStreaming) return;
    executeChatTurn(prompt);
  });

  // Clear chat
  clearChatBtn.addEventListener("click", () => {
    state.history = [];
    state.threadId = `thread-ts-${Math.random().toString(36).substring(2, 9)}`;
    activeThreadBadge.textContent = `Thread: #${state.threadId}`;
    chatMessages.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon">🤖</div>
        <h3>Chat Cleared</h3>
        <p>Conversation history and agent thread checkpoint reset. Ask a question to begin a new session!</p>
      </div>
    `;
  });

  // Refresh tools button
  btnRefreshTools.addEventListener("click", fetchTools);
}

// Preset remote URL helper
window.setRemoteUrl = function (url) {
  remoteUrlInput.value = url;
  state.remoteUrl = url;
};

// Quick prompt helper
window.sendQuickPrompt = function (prompt) {
  if (state.isStreaming) return;
  messageInput.value = prompt;
  messageInput.dispatchEvent(new Event("input"));
  executeChatTurn(prompt);
};

// Fetch registered tools
async function fetchTools() {
  try {
    const res = await fetch("/api/tools");
    if (!res.ok) return;
    const data = await res.json();
    const tools = data.tools || [];
    toolCount.textContent = tools.length;

    toolList.innerHTML = tools
      .map(
        (t) => `
        <div class="tool-card">
          <div class="tool-title"><code>${escapeHtml(t.name)}</code></div>
          <div class="tool-desc">${escapeHtml(t.description)}</div>
        </div>
      `
      )
      .join("");
  } catch (err) {
    console.warn("Could not fetch tools inventory:", err);
  }
}

// Core Chat Stream Execution
async function executeChatTurn(userPrompt) {
  // Clear welcome card if present
  const welcomeEl = chatMessages.querySelector(".welcome-message");
  if (welcomeEl) welcomeEl.remove();

  // 1. Render User Message
  appendUserMessage(userPrompt);
  state.history.push({ role: "user", content: userPrompt });

  messageInput.value = "";
  messageInput.style.height = "auto";
  setStreamingState(true);

  // 2. Prepare Assistant Message Container
  const { rowEl, textContainer, toolContainer } = createAssistantRow();
  chatMessages.appendChild(rowEl);
  scrollToBottom();

  // 3. Determine Endpoint & Payload
  const endpoint = state.pattern === "in-process" ? "/api/chat/in-process" : "/api/chat/remote";
  const payload = {
    prompt: userPrompt,
    messages: state.history,
    provider: state.provider,
    threadId: state.threadId,
    remoteUrl: state.pattern === "remote" ? state.remoteUrl : undefined,
  };

  let assistantContent = "";
  const activeToolCards = new Map();

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("No response body stream received.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          handleStreamEvent(event, {
            textContainer,
            toolContainer,
            activeToolCards,
            onToken: (tok) => {
              assistantContent += tok;
            },
          });
          scrollToBottom();
        } catch (jsonErr) {
          console.warn("JSON parse error on SSE event:", jsonErr, jsonStr);
        }
      }
    }

    // Save turn to history
    if (assistantContent) {
      state.history.push({ role: "assistant", content: assistantContent });
    }
  } catch (err) {
    const errCard = document.createElement("div");
    errCard.className = "error-card";
    errCard.textContent = `Error: ${err.message || String(err)}`;
    toolContainer.appendChild(errCard);
    scrollToBottom();
  } finally {
    setStreamingState(false);
  }
}

// Handle individual normalized SSE events
function handleStreamEvent(event, ctx) {
  const { textContainer, toolContainer, activeToolCards, onToken } = ctx;

  switch (event.event) {
    case "token": {
      onToken(event.content);
      textContainer.textContent += event.content;
      break;
    }

    case "tool_start": {
      const toolId = `${event.tool}-${Date.now()}`;
      const card = document.createElement("div");
      card.className = "tool-event-card";
      card.innerHTML = `
        <div class="tool-event-header">
          <span class="tool-badge running">
            <span class="tool-spinner"></span>
            Executing Tool: <strong>${escapeHtml(event.tool)}</strong>
          </span>
          <span style="font-size: 11px; color: var(--text-dim);">Running</span>
        </div>
        <div class="tool-payload">Input: ${escapeHtml(JSON.stringify(event.input))}</div>
      `;
      toolContainer.appendChild(card);
      activeToolCards.set(event.tool, card);
      break;
    }

    case "tool_end": {
      let card = activeToolCards.get(event.tool);
      if (!card) {
        card = document.createElement("div");
        card.className = "tool-event-card";
        toolContainer.appendChild(card);
      }
      card.innerHTML = `
        <div class="tool-event-header">
          <span class="tool-badge success">
            ✔ Tool Executed: <strong>${escapeHtml(event.tool)}</strong>
          </span>
          <span style="font-size: 11px; color: var(--accent-green);">Completed</span>
        </div>
        <div class="tool-payload">Result: ${escapeHtml(event.output)}</div>
      `;
      break;
    }

    case "error": {
      const errEl = document.createElement("div");
      errEl.className = "error-card";
      errEl.textContent = `Agent Error: ${event.error}`;
      toolContainer.appendChild(errEl);
      break;
    }

    case "done": {
      // Completed stream
      break;
    }
  }
}

// UI Helpers
function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="avatar avatar-user">You</div>
    <div class="message-content">${escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(row);
}

function createAssistantRow() {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const avatar = document.createElement("div");
  avatar.className = "avatar avatar-assistant";
  avatar.textContent = "AI";

  const contentWrap = document.createElement("div");
  contentWrap.className = "message-content";

  const toolContainer = document.createElement("div");
  toolContainer.className = "tool-container";

  const textContainer = document.createElement("div");
  textContainer.className = "text-stream";

  contentWrap.appendChild(toolContainer);
  contentWrap.appendChild(textContainer);

  row.appendChild(avatar);
  row.appendChild(contentWrap);

  return { rowEl: row, textContainer, toolContainer };
}

function setStreamingState(isStreaming) {
  state.isStreaming = isStreaming;
  sendBtn.disabled = isStreaming;
  messageInput.disabled = isStreaming;

  if (isStreaming) {
    statusText.textContent = "Agent Executing...";
    serviceStatus.querySelector(".status-dot").style.backgroundColor = "var(--accent-amber)";
  } else {
    statusText.textContent = "Ready";
    serviceStatus.querySelector(".status-dot").style.backgroundColor = "var(--accent-green)";
    messageInput.focus();
  }
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  if (typeof str !== "string") return String(str ?? "");
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

