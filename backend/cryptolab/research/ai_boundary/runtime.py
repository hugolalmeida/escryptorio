"""Bounded DEVELOPMENT_MOCK supervision. No filesystem or egress sandbox."""
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, fields
from pathlib import Path

from ..evidence.core import EvidenceError
from .gateway import make_request, validate_output


@dataclass(frozen=True)
class BudgetPolicy:
    max_input_bytes: int = 65536
    max_output_bytes: int = 65536
    max_calls: int = 4
    max_attempts: int = 1
    timeout_ms: int = 5000
    max_input_tokens: int = 16384
    max_output_tokens: int = 16384
    max_simulated_cost: int = 131072
    max_concurrency: int = 1

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 0 <= value <= 2**31 - 1:
                raise EvidenceError("BUDGET_POLICY_INVALID")
        if self.max_input_bytes > 65536 or self.max_output_bytes > 65536 or self.timeout_ms > 60000:
            raise EvidenceError("BUDGET_POLICY_INVALID")


class BudgetSession:
    """Thread-safe ephemeral reservations. Failed attempts retain their reserve."""

    def __init__(self, policy=None):
        self.policy = policy or BudgetPolicy()
        self._lock = threading.Lock()
        self._calls = 0
        self._active = 0
        self._cost = 0
        self._attempts = {}
        self._outcomes = []

    def reserve(self, request_id, input_bytes):
        if type(input_bytes) is not int or input_bytes < 0:
            raise EvidenceError("BUDGET_INPUT_INVALID")
        policy = self.policy
        input_tokens = (input_bytes + 3) // 4
        output_tokens = (policy.max_output_bytes + 3) // 4
        cost = input_tokens + output_tokens
        with self._lock:
            if (input_bytes > policy.max_input_bytes or input_tokens > policy.max_input_tokens
                or output_tokens > policy.max_output_tokens or policy.timeout_ms == 0
                or self._calls >= policy.max_calls or self._active >= policy.max_concurrency
                or self._attempts.get(request_id, 0) >= policy.max_attempts
                or self._cost + cost > policy.max_simulated_cost):
                raise EvidenceError("BUDGET_EXHAUSTED")
            self._calls += 1
            self._active += 1
            self._cost += cost
            self._attempts[request_id] = self._attempts.get(request_id, 0) + 1

    def finish(self, outcome, input_bytes, output_bytes):
        with self._lock:
            self._active -= 1
            self._outcomes.append({"outcome": outcome, "input_bytes": input_bytes,
                                   "output_bytes": output_bytes,
                                   "estimated_input_tokens": (input_bytes + 3) // 4,
                                   "estimated_output_tokens": (output_bytes + 3) // 4})

    def usage(self):
        with self._lock:
            return {"calls": self._calls, "active": self._active, "reserved_simulated_units": self._cost,
                    "outcomes": [dict(item) for item in self._outcomes]}


def require_mode(mode):
    if mode == "ISOLATED_RESEARCH":
        raise EvidenceError("ISOLATED_RESEARCH_UNAVAILABLE")
    if mode != "DEVELOPMENT_MOCK":
        raise EvidenceError("MODE_INVALID")


def _supervise(command, raw, policy, cancel, cwd, env, observed=None):
    """Internal transport, also exercised with trusted synthetic process fixtures."""
    process = None
    threads = []
    output = bytearray()
    exceeded = threading.Event()
    deadline = time.monotonic() + policy.timeout_ms / 1000
    observed = observed if observed is not None else {}

    def read(stream, target):
        total = 0
        while True:
            chunk = stream.read(1024)
            if not chunk:
                return
            total += len(chunk)
            if target is not None:
                observed["output_bytes"] = total
            if total > policy.max_output_bytes:
                exceeded.set()
                return
            if target is not None:
                target.extend(chunk)

    def write():
        try:
            process.stdin.write(raw)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    try:
        if cancel.is_set():
            raise EvidenceError("CANCELLED")
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=cwd, env=env, shell=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for function, args in ((read, (process.stdout, output)), (read, (process.stderr, None)), (write, ())):
            thread = threading.Thread(target=function, args=args, daemon=True)
            threads.append(thread)
            thread.start()
        while True:
            if cancel.is_set():
                raise EvidenceError("CANCELLED")
            if exceeded.is_set():
                raise EvidenceError("OUTPUT_SIZE_LIMIT")
            if time.monotonic() >= deadline:
                raise EvidenceError("WORKER_TIMEOUT")
            if process.poll() is not None and all(not t.is_alive() for t in threads):
                break
            cancel.wait(0.01)
        if process.returncode != 0:
            raise EvidenceError("WORKER_FAILED")
        return bytes(output)
    except OSError:
        raise EvidenceError("WORKER_UNAVAILABLE") from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            for thread in threads:
                thread.join(timeout=1)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()


def run_mock(context, request_id, session=None, cancel=None, mode="ISOLATED_RESEARCH"):
    require_mode(mode)
    request = make_request(context, request_id)
    session = session or BudgetSession()
    cancel = cancel or threading.Event()
    session.reserve(request_id, len(request))
    outcome = "FAILED"
    output = b""
    observed = {}
    try:
        with tempfile.TemporaryDirectory(prefix="research-mock-") as directory:
            # Only the fixed stdlib fixture is staged. No package import path,
            # credentials, bundle path or database is provided to this child.
            worker = Path(directory) / "mock_worker.py"
            worker.write_bytes(Path(__file__).with_name("mock_worker.py").read_bytes())
            env = {"TEMP": directory, "TMP": directory}
            if os.name == "nt":
                env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
            output = _supervise([sys.executable, "-I", "-S", str(worker)], request,
                                session.policy, cancel, directory, env, observed)
        result = validate_output(output, request, session.policy.max_output_bytes)
        if cancel.is_set():
            raise EvidenceError("CANCELLED")
        outcome = "APPROVED"
        return {**result, "mode": mode, "isolation": "NOT_SANDBOXED"}
    except EvidenceError as exc:
        if str(exc) == "CANCELLED":
            outcome = "CANCELLED"
        raise
    finally:
        session.finish(outcome, len(request), observed.get("output_bytes", 0))
