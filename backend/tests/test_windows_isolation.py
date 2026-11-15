"""Authorized benign Windows PoC, synthetic files and loopback only."""
import ctypes as c
from dataclasses import replace
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

import pytest

from cryptolab.research.ai_boundary.isolation_poc import Child, IsolationPolicy, PocEnvironment
from cryptolab.research.ai_boundary.windows_native import Native, WindowsErrorCode
from cryptolab.research.ai_boundary.runtime import require_mode
from cryptolab.research.evidence.core import EvidenceError
from test_backtest import research
from test_evidence_backtest import frozen, metric_body

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Real Windows APIs required")


@pytest.fixture(scope="module")
def environment():
    with PocEnvironment() as result:
        yield result
    assert result.cleanup_state == "COMPLETE"
    assert not result.root.exists()


def resource_policy(**updates):
    return replace(IsolationPolicy(identity="JOB_ONLY"), **updates)


def decoded(result):
    assert result["status"] == "EXITED", {k: v for k, v in result.items() if k != "stdout"}
    assert result["rollback"] == "COMPLETE"
    return json.loads(result["stdout"])


def test_discovery_and_normal_process(environment, monkeypatch):
    assert environment.discovery["elevated"] is False
    assert environment.discovery["token_type"] == 1
    assert environment.discovery["restricted_token_creation"] == "AVAILABLE"
    monkeypatch.setenv("FAKE_PRIVATE_TOKEN", "SYNTHETIC_ENV_CANARY")
    result = environment.run("normal", policy=resource_policy())
    assert decoded(result)["ok"] and decoded(result)["canary_environment_absent"]
    assert result["max_active_job_processes"] == 1
    assert 0 < result["peak_job_bytes"] < result["policy"]["job_memory_bytes"]
    assert b"SYNTHETIC_ENV_CANARY" not in result["stdout"]


def test_os_memory_limit_with_positive_control(environment):
    restricted = environment.run("memory", policy=resource_policy())
    permitted = environment.run("memory", policy=resource_policy(
        process_memory_bytes=192 * 1024**2, job_memory_bytes=256 * 1024**2))
    assert decoded(restricted)["allocated"] is False
    assert decoded(restricted)["winerror"] in (8, 1455)
    assert decoded(permitted)["allocated"] is True
    assert restricted["peak_job_bytes"] < 64 * 1024**2
    assert permitted["peak_job_bytes"] >= 96 * 1024**2


def test_job_wide_memory_limit_independently(environment):
    policy = resource_policy(process_memory_bytes=192 * 1024**2, job_memory_bytes=192 * 1024**2)
    # Independent Job cap verified by read-back even when process cap is larger
    # in the native structure. Only this test uses the low-level owned Job.
    native = environment.native
    job = native.job(policy)
    try:
        limits = native.job_limits(job)
        limits.JobMemoryLimit = 64 * 1024**2
        native.check(native.kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)), "SetInformationJobObject")
        assert native.job_limits(job).JobMemoryLimit == 64 * 1024**2
        child = Child(native)
        try:
            streams = child.launch(environment.root, "memory", job, environment.sid, policy)
            streams[0].write(b"{}")
            streams[0].close()
            assert native.kernel.WaitForSingleObject(child.process, 5000) == 0
            allocation = json.loads(streams[1].read())
            assert allocation["allocated"] is False and allocation["winerror"] in (8, 1455)
            assert native.job_limits(job).JobMemoryLimit == 64 * 1024**2
        finally:
            native.check(native.kernel.TerminateJobObject(job, 124), "TerminateJobObject")
            assert child.cleanup() == []
    finally:
        native.close(job)


def test_process_limit_and_descendant_termination(environment):
    denied = environment.run("descendant", policy=resource_policy())
    assert decoded(denied) == {"spawned": False, "winerror": 1816}
    permitted = environment.run("descendant", policy=resource_policy(active_processes=2, timeout_ms=900))
    assert json.loads(permitted["stdout"])["spawned"] is True
    assert permitted["status"] == "TIMEOUT"
    assert permitted["max_active_job_processes"] == 2
    assert permitted["rollback"] == "COMPLETE"


@pytest.mark.parametrize("operation,status", [("sleep", "TIMEOUT"), ("stdout", "OUTPUT_LIMIT"),
    ("stderr", "OUTPUT_LIMIT"), ("exit", "FAILED")])
def test_supervisor_limits(environment, operation, status):
    result = environment.run(operation, policy=resource_policy(timeout_ms=800))
    assert result["status"] == status
    assert result["rollback"] == "COMPLETE"
    assert len(result["stdout"]) <= 65536
    if operation == "exit":
        assert result["exit_code"] == 7


def test_running_cancel_and_concurrency(environment):
    cancel = threading.Event()
    responses = queue.Queue()
    thread = threading.Thread(target=lambda: responses.put(environment.run(
        "sleep", policy=resource_policy(), cancel=cancel)))
    thread.start()
    try:
        # The lock belongs to the supervisor and is acquired before launch.
        deadline = time.monotonic() + 2
        while not environment._run_lock.locked() and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        with pytest.raises(EvidenceError, match="CONCURRENCY"):
            environment.run("normal", policy=resource_policy())
        cancel.set()
        thread.join(5)
        result = responses.get(timeout=1)
        assert result["status"] == "CANCELLED" and result["rollback"] == "COMPLETE"
    finally:
        cancel.set()
        thread.join(5)


@pytest.mark.parametrize("identity", ["RESTRICTED_TOKEN", "APPCONTAINER"])
def test_identity_attempts_are_fail_closed(environment, identity):
    # Results describe actual host capability. A startup failure proves no file
    # or network denial, and must remain a failed attempt with complete rollback.
    result = environment.run("token", policy=IsolationPolicy(identity=identity))
    assert result["rollback"] == "COMPLETE"
    assert result["policy"]["identity"] == identity
    if result["status"] == "EXITED":
        assert decoded(result)["appcontainer"] is (identity == "APPCONTAINER")
    else:
        assert result["status"] == "FAILED"
        assert result["api_error"] is not None or result["exit_code"] != 0
        assert result["stdout"] == b""


def test_filesystem_probes_and_canary_nonmutation(environment):
    original = {p.name: p.read_bytes() for p in (environment.root / "protected").iterdir()}
    for identity in ("RESTRICTED_TOKEN", "APPCONTAINER"):
        result = environment.run("filesystem", policy=IsolationPolicy(identity=identity))
        assert result["rollback"] == "COMPLETE"
        if result["status"] == "EXITED":
            response = decoded(result)
            assert response.pop("allowed_read") is True
            assert set(response.values()) == {5}  # ACCESS_DENIED, not missing path.
        else:
            assert result["stdout"] == b""  # Property remains NOT_VERIFIED.
    assert original == {p.name: p.read_bytes() for p in (environment.root / "protected").iterdir()}


def test_loopback_control_and_restricted_attempt(environment):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(8)
        server.settimeout(0.2)
        port = server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            connection, _ = server.accept()
            connection.close()
        payload = json.dumps({"port": port}).encode()
        # Explicit positive control. No synthetic secrets are sent over sockets.
        assert decoded(environment.run("network", payload, resource_policy())) == {"loopback": 0, "tcp_local": 0}
        for _ in range(2):
            connection, _ = server.accept()
            connection.close()
        result = environment.run("network", payload, IsolationPolicy())
        if result["status"] == "EXITED":
            assert set(decoded(result).values()) == {10013}
        else:
            assert result["status"] == "FAILED" and result["stdout"] == b""
        with pytest.raises(socket.timeout):
            server.accept()
        assert result["rollback"] == "COMPLETE"


@pytest.mark.parametrize("method", ["CreateJobObjectW", "SetInformationJobObject", "AssignProcessToJobObject",
    "UpdateSecurityCapabilities"])
def test_failure_before_resume_rolls_back(environment, monkeypatch, method):
    native = environment.native
    before = native.handle_count()
    original_check = native.check
    def fail(value, api):
        if api == method:
            # Failure injection occurs at a checked boundary. For Job creation,
            # close the actually-created fixture handle before simulating error.
            if api == "CreateJobObjectW" and value:
                native.close(value)
            raise WindowsErrorCode(api, 5)
        return original_check(value, api)
    with monkeypatch.context() as patch:
        patch.setattr(native, "check", fail)
        result = environment.run("normal", policy=IsolationPolicy() if method == "UpdateSecurityCapabilities" else resource_policy())
    assert result["status"] == "FAILED" and result["rollback"] == "COMPLETE"
    assert result["stdout"] == b""
    assert native.handle_count() == before
    assert decoded(environment.run("normal", policy=resource_policy()))["ok"]


def test_rollback_failure_is_not_success(monkeypatch):
    instance = PocEnvironment().__enter__()
    native = instance.native
    close = native.close
    calls = 0
    def fail_once(handle):
        nonlocal calls
        close(handle)
        calls += 1
        # Final Job close after normal launch pipe/thread handles are released.
        if calls == 6:
            raise WindowsErrorCode("SyntheticCloseFailure", 5)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(native, "close", fail_once)
            result = instance.run("normal", policy=resource_policy())
        assert result["status"] == "ROLLBACK_INCOMPLETE"
        assert result["rollback"] == "INCOMPLETE"
        with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
            instance.run("normal", policy=resource_policy())
    finally:
        with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
            instance.__exit__(None, None, None)
    assert instance.cleanup_state == "ROLLBACK_INCOMPLETE" and not instance.root.exists()


def test_invalid_output_cannot_claim_enforcement(environment):
    malformed = environment.run("invalid_json", policy=resource_policy())
    with pytest.raises(json.JSONDecodeError):
        json.loads(malformed["stdout"])
    forged = environment.run("forged_security", policy=resource_policy())
    assert decoded(forged)["security"] == "ENFORCED_AND_TESTED"
    assert "security" not in forged  # Supervisor has granted no guarantee.


def test_policy_input_and_production_gate(environment):
    assert IsolationPolicy().content_hash == IsolationPolicy().content_hash
    for change in ({"process_memory_bytes": -1}, {"active_processes": 0}, {"timeout_ms": True},
                   {"identity": "READ_SECRET"}, {"max_output_bytes": 65537}):
        with pytest.raises(EvidenceError):
            IsolationPolicy(**change)
    with pytest.raises(TypeError):
        IsolationPolicy(command="arbitrary")
    with pytest.raises(EvidenceError, match="INPUT_LIMIT"):
        environment.run("normal", b"x" * 65537)
    with pytest.raises(EvidenceError, match="OPERATION_INVALID"):
        environment.run("EXECUTE_COMMAND")
    with pytest.raises(EvidenceError, match="UNAVAILABLE"):
        require_mode("ISOLATED_RESEARCH")


def test_cli_discovery_and_invalid_arguments(capsys):
    from cryptolab.research.ai_boundary.isolation_poc import main
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["elevated"] is False
    assert main(["--SYNTHETIC_CANARY_INVALID_ARGUMENT"]) == 2
    message = capsys.readouterr()
    assert "SYNTHETIC_CANARY_INVALID_ARGUMENT" not in message.out + message.err


def test_repeated_runs_release_native_handles(environment):
    before = environment.native.handle_count()
    for _ in range(4):
        assert decoded(environment.run("normal", policy=resource_policy()))["ok"]
    assert environment.native.handle_count() == before


@pytest.mark.parametrize("failure", ["dacl", "write"])
def test_environment_failure_rolls_back(monkeypatch, failure):
    instance = PocEnvironment()
    with monkeypatch.context() as patch:
        if failure == "dacl":
            def denied(*args):
                raise WindowsErrorCode("SyntheticDaclFailure", 5)
            patch.setattr(instance.native, "apply_dacl", denied)
        else:
            original = Path.write_bytes
            def failed_write(path, data):
                if path.name == "context.json":
                    raise OSError("synthetic")
                return original(path, data)
            patch.setattr(Path, "write_bytes", failed_write)
        with pytest.raises((WindowsErrorCode, OSError)):
            instance.__enter__()
    assert instance.cleanup_state == "COMPLETE" and not instance.root.exists()


def test_directory_cleanup_failure_is_reported(monkeypatch):
    instance = PocEnvironment().__enter__()
    def fail():
        raise OSError("synthetic")
    with monkeypatch.context() as patch:
        patch.setattr(instance.directory, "cleanup", fail)
        with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
            instance.__exit__(None, None, None)
    assert instance.cleanup_state == "ROLLBACK_INCOMPLETE"
    instance.__exit__(None, None, None)
    assert instance.cleanup_state == "COMPLETE" and not instance.root.exists()


def test_interruption_after_launch_releases_owned_process(environment, monkeypatch):
    original = Child.launch
    before = environment.native.handle_count()
    def interrupt(child, *args):
        original(child, *args)
        raise KeyboardInterrupt()
    with monkeypatch.context() as patch:
        patch.setattr(Child, "launch", interrupt)
        with pytest.raises(KeyboardInterrupt):
            environment.run("normal", policy=resource_policy())
    assert environment.native.handle_count() == before
    assert decoded(environment.run("normal", policy=resource_policy()))["ok"]


def test_context_gateway_and_synthetic_database_nonmutation(environment, frozen, research, tmp_path):
    from cryptolab.research.ai_boundary.context import build_context
    from cryptolab.research.ai_boundary.gateway import make_request, validate_output
    from cryptolab.research.evidence.bundle_v2 import export
    from cryptolab.research.evidence.claims import claim
    service, _ = research
    with service.store.connect() as database:
        before = list(database.iterdump())
    source, result, asof = frozen
    bundle = tmp_path / "bundle"
    export(bundle, source, [claim(metric_body(result))], asof, asof, asof)
    original = {p.name: p.read_bytes() for p in bundle.iterdir()}
    context = build_context(bundle)
    request = make_request(context, "poc-synthetic-integration")
    response = environment.run("mock", request, resource_policy())
    assert response["rollback"] == "COMPLETE" and response["status"] == "EXITED"
    assert validate_output(response["stdout"], request, 65536)["status"] == "VALIDATED_MOCK"
    with service.store.connect() as database:
        assert before == list(database.iterdump())
    assert original == {p.name: p.read_bytes() for p in bundle.iterdir()}


def test_kill_on_supervisor_exit_and_descendant(environment):
    # This fixed trusted helper owns the Job, while the parent owns the synthetic
    # directory. Killing only this helper closes the last non-inherited Job handle.
    code = '''
import ctypes as c, json, sys, time
from pathlib import Path
from cryptolab.research.ai_boundary.isolation_poc import Child,IsolationPolicy
from cryptolab.research.ai_boundary.windows_native import Native
n=Native()
job=n.job(IsolationPolicy(identity="JOB_ONLY",active_processes=2))
child=Child(n)
streams=child.launch(Path(sys.argv[1]),"descendant",job,None,IsolationPolicy(identity="JOB_ONLY",active_processes=2))
streams[0].write(b"{}")
streams[0].close()
deadline=time.monotonic()+5
while n.job_accounting(job).ActiveProcesses != 2 and time.monotonic()<deadline:
    time.sleep(.01)
print(json.dumps(n.job_pids(job)),flush=True)
time.sleep(20)
'''
    helper = subprocess.Popen([sys.executable, "-c", code, str(environment.root)],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              env={"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                                   "SystemDrive": Path(os.environ.get("SystemRoot", r"C:\Windows")).drive,
                                   "TEMP": str(environment.root / "outputs"),
                                   "TMP": str(environment.root / "outputs"),
                                   "LIVE_TRADING_ENABLED": "false", "PAPER_SIMULATION_ENABLED": "false"},
                              cwd=environment.root / "outputs",
                              creationflags=subprocess.CREATE_NO_WINDOW)
    handles = []
    messages = queue.Queue()
    reader = threading.Thread(target=lambda: messages.put(helper.stdout.readline()), daemon=True)
    reader.start()
    try:
        pids = json.loads(messages.get(timeout=8))
        assert len(pids) == 2
        for pid in pids:
            handle = environment.native.check(environment.native.kernel.OpenProcess(0x100000, False, pid), "OpenOwnedProcess")
            handles.append(handle)
            assert environment.native.kernel.WaitForSingleObject(handle, 0) == 258
        helper.kill()
        helper.wait(timeout=5)
        for handle in handles:
            assert environment.native.kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        if helper.poll() is None:
            helper.kill()
        helper.wait(timeout=5)
        reader.join(2)
        helper.stdout.close()
        for handle in handles:
            environment.native.close(handle)
