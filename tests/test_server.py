from unittest.mock import Mock

import pytest

from utils import server


@pytest.fixture
def runner(monkeypatch):
    runner = server.ADKAgentRunner()
    monkeypatch.setattr(runner, "_is_server_running", lambda: False)
    monkeypatch.setattr(server.atexit, "register", lambda callback: None)
    monkeypatch.setattr(server.time, "sleep", lambda seconds: None)
    yield runner
    runner.stop_server()


def test_server_output_uses_a_file_and_stop_closes_it(runner, monkeypatch):
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr(server.subprocess, "Popen", launch)
    monkeypatch.setattr(server.requests, "get", Mock(return_value=Mock(status_code=200)))

    runner.start_server()
    output = launch.call_args.kwargs["stdout"]
    assert output is not server.subprocess.PIPE
    assert not output.closed
    assert launch.call_args.kwargs["stderr"] == server.subprocess.STDOUT

    runner.stop_server()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)
    assert output.closed
    assert runner.server_process is None
    assert runner._server_log is None


def test_failed_launch_closes_output(runner, monkeypatch):
    outputs = []

    def fail_launch(*args, **kwargs):
        outputs.append(kwargs["stdout"])
        raise FileNotFoundError("adk executable missing")

    monkeypatch.setattr(server.subprocess, "Popen", fail_launch)
    with pytest.raises(RuntimeError, match="adk executable missing"):
        runner.start_server()
    assert outputs[0].closed
    assert runner._server_log is None


def test_early_exit_includes_diagnostics_and_cleans_up(runner, monkeypatch):
    process = Mock()
    process.poll.return_value = 1
    outputs = []

    def failed_server(*args, **kwargs):
        output = kwargs["stdout"]
        outputs.append(output)
        output.write("Invalid agent configuration\n")
        return process

    monkeypatch.setattr(server.subprocess, "Popen", failed_server)
    with pytest.raises(RuntimeError, match="Invalid agent configuration"):
        runner.start_server()
    assert outputs[0].closed
    assert runner.server_process is None


def test_stop_kills_and_waits_for_unresponsive_process(runner):
    process = Mock()
    process.wait.side_effect = [server.subprocess.TimeoutExpired("adk", 5), 0]
    runner.server_process = process
    runner._we_started_server = True

    runner.stop_server()

    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    process.wait.assert_called_with(timeout=3)
    assert runner.server_process is None
