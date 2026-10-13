"""Convenience Launcher for the Streamlit & LangChain Agent Showcase.

Usage:
    # Run Pattern A or Frontend only:
    uv run python -m src.langchain_suite.frontend_agent.run_showcase --frontend

    # Run FastAPI SSE Backend:
    uv run python -m src.langchain_suite.frontend_agent.run_showcase --backend

    # Run both services simultaneously:
    uv run python -m src.langchain_suite.frontend_agent.run_showcase --all
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_backend(port: int = 8000) -> subprocess.Popen:
    print(f"🚀 Starting Decoupled FastAPI SSE Microservice on http://localhost:{port}...")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.langchain_suite.frontend_agent.backend.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]
    return subprocess.Popen(cmd)


def run_frontend(port: int = 8501) -> subprocess.Popen:
    app_path = Path(__file__).parent / "frontend" / "app.py"
    print(f"✨ Starting Streamlit Chat Application on http://localhost:{port}...")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    return subprocess.Popen(cmd)


def main():
    parser = argparse.ArgumentParser(description="Launcher for Streamlit Agent Showcase")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backend", action="store_true", help="Run the FastAPI SSE backend on port 8000")
    group.add_argument("--frontend", action="store_true", help="Run the Streamlit frontend on port 8501")
    group.add_argument("--all", action="store_true", help="Run both FastAPI backend and Streamlit frontend")

    args = parser.parse_args()

    procs = []
    try:
        if args.backend:
            p = run_backend()
            p.wait()
        elif args.frontend:
            p = run_frontend()
            p.wait()
        elif args.all:
            p_be = run_backend()
            procs.append(p_be)
            time.sleep(1.5)  # allow backend to bind port
            p_fe = run_frontend()
            procs.append(p_fe)
            print("\n✅ Both services are running! Press Ctrl+C to terminate both.\n")
            p_fe.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down showcase services...")
    finally:
        for p in procs:
            p.terminate()
            p.wait()


if __name__ == "__main__":
    main()

