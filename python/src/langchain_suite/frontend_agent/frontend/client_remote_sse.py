"""Remote SSE Client for consuming agent events from the FastAPI microservice."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional
import httpx


class RemoteSseAgentClient:
    """Client for streaming agent lifecycle events from the decoupled FastAPI backend."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def check_health(self) -> Dict[str, Any]:
        """Verify if backend microservice is reachable and get inventory."""
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()

    def get_tools(self) -> List[Dict[str, Any]]:
        """Fetch registered tool metadata from backend."""
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{self.base_url}/tools")
            resp.raise_for_status()
            return resp.json()

    def stream_chat(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        provider: str = "mock",
        model: Optional[str] = None,
        thread_id: str = "default-session",
        timeout: float = 60.0,
    ) -> Iterator[Dict[str, Any]]:
        """Connects to /agent/chat/stream and yields normalized lifecycle event dicts.

        Yields events:
        - {"event": "token", "content": "..."}
        - {"event": "tool_start", "tool": "...", "input": {...}}
        - {"event": "tool_end", "tool": "...", "output": "..."}
        - {"event": "done", "status": "completed"}
        - {"event": "error", "error": "..."}
        """
        url = f"{self.base_url}/agent/chat/stream"
        payload = {
            "prompt": prompt,
            "messages": messages,
            "provider": provider,
            "model": model,
            "thread_id": thread_id,
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_detail = response.read().decode("utf-8", errors="replace")
                        yield {
                            "event": "error",
                            "error": f"HTTP {response.status_code}: {error_detail}",
                        }
                        return

                    current_event_type = "message"
                    data_buffer = []

                    for line in response.iter_lines():
                        line = line.strip()
                        if not line:
                            # Empty line indicates end of an SSE message block
                            if data_buffer:
                                combined_data = "".join(data_buffer)
                                try:
                                    parsed = json.loads(combined_data)
                                    yield parsed
                                except json.JSONDecodeError:
                                    yield {
                                        "event": current_event_type,
                                        "content": combined_data,
                                    }
                                data_buffer.clear()
                                current_event_type = "message"
                            continue

                        if line.startswith("event:"):
                            current_event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            data_buffer.append(line[len("data:"):].strip())

        except httpx.ConnectError:
            yield {
                "event": "error",
                "error": f"Could not connect to backend at {self.base_url}. Ensure the FastAPI server is running.",
            }
        except Exception as exc:
            yield {
                "event": "error",
                "error": f"Remote SSE stream error: {str(exc)}",
            }

