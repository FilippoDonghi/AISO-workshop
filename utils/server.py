"""
Google ADK Agent Runner using API Server.
This module provides a function to run the ADK agent via HTTP requests to the API server.
"""

import atexit
import os
import subprocess
import tempfile
import time
import uuid
from typing import Any, TextIO

import requests


class ADKAgentRunner:
    """
    Client for interacting with ADK agent via FastAPI server.
    Automatically starts and manages the API server lifecycle.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        agent_name: str = "my_agent",
        user_id: str = "dev_user",
    ):
        self.base_url = base_url
        self.agent_name = agent_name
        self.user_id = user_id  # User ID for sessions (use same as web UI to see eval chats there)
        self.server_process = None
        self._server_log: TextIO | None = None
        self._we_started_server = False  # Track if we started the server

    def _close_server_log(self) -> None:
        if self._server_log is not None:
            self._server_log.close()
            self._server_log = None

    def _server_log_tail(self, limit: int = 2_000) -> str:
        if self._server_log is None:
            return ""
        self._server_log.flush()
        self._server_log.seek(0)
        return self._server_log.read()[-limit:].strip()

    def _terminate_server_process(self) -> None:
        if self.server_process is None:
            return
        self.server_process.terminate()
        try:
            self.server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server_process.kill()
            self.server_process.wait(timeout=3)
        self.server_process = None
        self._we_started_server = False

    def _is_server_running(self) -> bool:
        """Check if an ADK API server is already running."""
        try:
            response = requests.get(f"{self.base_url}/list-apps", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def start_server(self):
        """Start the ADK API server in the background if not already running."""
        # First check if a server is already running
        if self._is_server_running():
            print(f"✓ Using existing ADK API server at {self.base_url}")
            return

        if self.server_process is not None:
            print("Server process already started by us")
            return

        print("Starting ADK API server...")
        self._close_server_log()
        # Owned across start/stop calls; closed on every shutdown and startup failure.
        self._server_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")  # noqa: SIM115
        try:
            self.server_process = subprocess.Popen(
                ["adk", "api_server", "--host", "127.0.0.1", "--port", "8000", "."],
                stdout=self._server_log,
                stderr=subprocess.STDOUT,
                cwd=os.getcwd(),
            )
        except OSError as error:
            self._close_server_log()
            raise RuntimeError(f"Failed to start the ADK API server: {error}") from error

        self._we_started_server = True

        # Register cleanup on exit (only if we started it)
        atexit.register(self.stop_server)

        # Wait for server to be ready
        max_retries = 30
        for _ in range(max_retries):
            if self.server_process.poll() is not None:
                break
            try:
                response = requests.get(f"{self.base_url}/list-apps", timeout=1)
                if response.status_code == 200:
                    print(f"✓ ADK API server started successfully on {self.base_url}")
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)

        self._terminate_server_process()
        log_tail = self._server_log_tail()
        self._close_server_log()
        detail = f"\nServer output:\n{log_tail}" if log_tail else ""
        raise RuntimeError(f"Failed to start ADK API server{detail}")

    def stop_server(self):
        """Stop the ADK API server (only if we started it)."""
        if self.server_process is not None and self._we_started_server:
            print("\nStopping ADK API server...")
            self._terminate_server_process()
        self._close_server_log()

    def restart_server(self):
        """Gracefully stop the server and start a fresh one."""
        print("\nRestarting ADK API server after a transport failure...")
        self._terminate_server_process()
        self._close_server_log()
        time.sleep(2)
        self.start_server()

    @staticmethod
    def _extract_response_details(
        events: list[dict[str, Any]],
    ) -> tuple[str, list[str]]:
        """Extract response text and tool call names from ADK events."""
        response_parts: list[str] = []
        tool_calls: list[str] = []

        for event in events:
            content = event.get("content")
            if not content:
                continue
            parts = content.get("parts", [])
            for part in parts:
                text = part.get("text")
                if text:
                    response_parts.append(text)

                function_call = part.get("functionCall")
                if function_call:
                    name = function_call.get("name", "")
                    if name:
                        tool_calls.append(name)

        return "".join(response_parts).strip(), tool_calls

    def run_agent(self, question: str, file_paths: list[str] | None = None) -> dict[str, Any]:
        """Run agent and return response text plus tool calls metadata."""
        if self.server_process is None and not self._is_server_running():
            self.start_server()

        session_id = f"eval_{uuid.uuid4().hex[:12]}"

        try:
            session_response = requests.post(
                f"{self.base_url}/apps/{self.agent_name}/users/{self.user_id}/sessions/{session_id}",
                json={"state": {}},
                timeout=10,
            )
            session_response.raise_for_status()
        except requests.exceptions.RequestException as error:
            if self._we_started_server and isinstance(
                error,
                (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            ):
                self.restart_server()
            raise RuntimeError(
                f"Failed to create session for agent '{self.agent_name}': {error}"
            ) from error

        message_parts = [{"text": question}]
        if file_paths:
            file_info = f"\n\nNote: The following files are relevant: {', '.join(file_paths)}"
            message_parts[0]["text"] += file_info

        # Send message using /run endpoint
        try:
            response = requests.post(
                f"{self.base_url}/run",
                json={
                    "app_name": self.agent_name,
                    "user_id": self.user_id,
                    "session_id": session_id,
                    "new_message": {
                        "role": "user",
                        "parts": message_parts,
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
            events = response.json()
            response_text, tool_calls = self._extract_response_details(events)
            return {
                "response_text": response_text,
                "tool_calls": tool_calls,
                "session_id": session_id,
            }
        except requests.exceptions.RequestException as error:
            if self._we_started_server and isinstance(
                error,
                (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            ):
                self.restart_server()
            error_message = str(error)
            if hasattr(error, "response") and error.response is not None:
                body = error.response.text.strip()
                if body:
                    error_message = f"{error_message} | body: {body[:500]}"
            raise RuntimeError(f"Failed to run agent on question: {error_message}") from error


# Global runner instance
_runner = None


def run_agent(
    question: str, file_paths: list[str] | None = None, user_id: str = "dev_user"
) -> dict[str, Any]:
    """
    Run the Google ADK agent on a given question.
    This function manages the API server lifecycle automatically.

    Args:
        question: The question to answer
        file_paths: Optional list of file paths that may be needed to answer the question
        user_id: User ID for the session (default: "dev_user"). Use same as web UI to see eval chats there.

    Returns:
        The agent's response as a string
    """
    global _runner

    if _runner is None:
        _runner = ADKAgentRunner(user_id=user_id)
        _runner.start_server()

    return _runner.run_agent(question, file_paths)
