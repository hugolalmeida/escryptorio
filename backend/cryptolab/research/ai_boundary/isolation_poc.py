"""Experimental synthetic Windows containment. Production isolated mode stays closed."""
import ctypes as c
from ctypes import wintypes as w
from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile

from ..evidence.core import EvidenceError, digest, strict_json
from .windows_native import (Native, WindowsErrorCode, PROCESS_INFORMATION, SECURITY_ATTRIBUTES,
                             SECURITY_CAPABILITIES, SID_AND_ATTRIBUTES, STARTUPINFOEX)

PROBES = {"normal", "token", "memory", "filesystem", "network", "descendant", "sleep",
          "stdout", "stderr", "invalid_json", "forged_security", "exit", "mock", "outputs"}


@dataclass(frozen=True)
class IsolationPolicy:
    schema_version: int = 1
    launcher_version: str = "windows-isolation-poc/1"
    process_memory_bytes: int = 64 * 1024 * 1024
    job_memory_bytes: int = 96 * 1024 * 1024
    active_processes: int = 1
    timeout_ms: int = 3000
    max_input_bytes: int = 65536
    max_output_bytes: int = 65536
    identity: str = "APPCONTAINER"

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "launcher_version":
                if type(value) is not str or value != "windows-isolation-poc/1":
                    raise EvidenceError("ISOLATION_POLICY_INVALID")
            elif field.name == "identity":
                if type(value) is not str or value not in ("JOB_ONLY", "RESTRICTED_TOKEN", "APPCONTAINER"):
                    raise EvidenceError("ISOLATION_POLICY_INVALID")
            elif type(value) is not int:
                raise EvidenceError("ISOLATION_POLICY_INVALID")
        if (self.schema_version != 1 or not 32 * 1024**2 <= self.process_memory_bytes <= 256 * 1024**2
            or not self.process_memory_bytes <= self.job_memory_bytes <= 256 * 1024**2
            or self.active_processes not in (1, 2) or not 100 <= self.timeout_ms <= 10000
            or not 1 <= self.max_input_bytes <= 65536 or not 1 <= self.max_output_bytes <= 65536):
            raise EvidenceError("ISOLATION_POLICY_INVALID")

    @property
    def content_hash(self):
        return digest("escryptorio:isolation-policy:v1", asdict(self))


class Child:
    """Owns native handles and converted CRT streams, including partial launches."""
    def __init__(self, native, resources=None):
        self.native = native
        self.handles = []
        self.streams = []
        self.process = None
        self.thread = None
        self.pid = None
        self.assigned = False
        self.resumed = False
        self.exit_code = None
        self.resources = resources
        if resources is not None:
            resources.bind_child(self)

    def own(self, handle):
        if self.resources is not None:
            self.resources.track(handle)
        self.handles.append(handle)
        return handle

    def close_handle(self, handle):
        try:
            self.native.close(handle)
        except WindowsErrorCode:
            if self.resources is not None:
                self.resources.close_failed(handle)
            raise
        if self.resources is not None:
            self.resources.closed(handle)
        self.handles.remove(handle)

    def adopt(self, info):
        self.process = self.own(info.hProcess)
        self.thread = self.own(info.hThread)
        self.pid = info.dwProcessId

    def pipe(self, parent_reads):
        read, write = w.HANDLE(), w.HANDLE()
        attributes = SECURITY_ATTRIBUTES(c.sizeof(SECURITY_ATTRIBUTES), None, True)
        self.native.check(self.native.kernel.CreatePipe(c.byref(read), c.byref(write), c.byref(attributes), 0), "CreatePipe")
        self.own(read.value)
        self.own(write.value)
        parent, child = (read.value, write.value) if parent_reads else (write.value, read.value)
        self.native.check(self.native.kernel.SetHandleInformation(parent, 1, 0), "SetHandleInformation")
        return parent, child

    def stream(self, handle, mode):
        import msvcrt
        descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY)
        self.handles.remove(handle)  # Ownership transferred to CRT descriptor.
        try:
            stream = os.fdopen(descriptor, mode, buffering=0)
        except BaseException:
            os.close(descriptor)
            if self.resources is not None:
                self.resources.closed(handle)
            raise
        self.streams.append(stream)
        if self.resources is not None:
            self.resources.transferred(handle, stream)
        return stream

    def launch(self, root, operation, job, sid, policy):
        n = self.native
        if self.resources is not None:
            self.resources.require_launch(root, job)
        parent_in, child_in = self.pipe(False)
        parent_out, child_out = self.pipe(True)
        parent_err, child_err = self.pipe(True)
        inheritance = (w.HANDLE * 3)(child_in, child_out, child_err)
        capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
        size = c.c_size_t()
        c.set_last_error(0)
        result = n.kernel.InitializeProcThreadAttributeList(None, 2 if policy.identity == "APPCONTAINER" else 1, 0, c.byref(size))
        if result or c.get_last_error() != 122:
            raise WindowsErrorCode("InitializeAttributeSize")
        attribute_buffer = c.create_string_buffer(size.value)
        n.check(n.kernel.InitializeProcThreadAttributeList(attribute_buffer, 2 if policy.identity == "APPCONTAINER" else 1,
                                                         0, c.byref(size)), "InitializeAttributes")
        try:
            n.check(n.kernel.UpdateProcThreadAttribute(attribute_buffer, 0, 0x20002, inheritance,
                                                      c.sizeof(inheritance), None, None), "UpdateHandleList")
            if policy.identity == "APPCONTAINER":
                n.check(n.kernel.UpdateProcThreadAttribute(attribute_buffer, 0, 0x20009, c.byref(capabilities),
                                                          c.sizeof(capabilities), None, None), "UpdateSecurityCapabilities")
            startup = STARTUPINFOEX()
            startup.StartupInfo.cb = c.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100
            startup.StartupInfo.hStdInput = child_in
            startup.StartupInfo.hStdOutput = child_out
            startup.StartupInfo.hStdError = child_err
            startup.lpAttributeList = c.addressof(attribute_buffer)
            executable = root / "worker" / "pythonw.exe"
            script = "mock_worker.py" if operation == "mock" else "isolation_probe.py"
            arguments = [str(executable), "-I", "-S", "-B", script]
            if operation != "mock":
                arguments.append(operation)
            command = c.create_unicode_buffer(subprocess.list2cmdline(arguments))
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            values = {"LIVE_TRADING_ENABLED": "false", "PAPER_SIMULATION_ENABLED": "false",
                      "SystemRoot": system_root, "SystemDrive": Path(system_root).drive,
                      "TEMP": str(root / "outputs"), "TMP": str(root / "outputs")}
            environment = c.create_unicode_buffer("\0".join(
                f"{key}={value}" for key, value in sorted(values.items(), key=lambda item: item[0].casefold())) + "\0\0")
            info = PROCESS_INFORMATION()
            flags = 0x4 | 0x400 | 0x80000 | 0x08000000  # Suspended, Unicode, extended, hidden.
            if policy.identity == "RESTRICTED_TOKEN":
                token = self.own(n.current_token())
                restricted = w.HANDLE()
                restricting_sid = c.c_void_p()
                try:
                    n.check(n.advapi.ConvertStringSidToSidW("S-1-5-12", c.byref(restricting_sid)), "ConvertRestrictingSid")
                    restricting = SID_AND_ATTRIBUTES(restricting_sid, 0)
                    n.check(n.advapi.CreateRestrictedToken(token, 1, 0, None, 0, None, 1,
                                                          c.byref(restricting), c.byref(restricted)), "CreateRestrictedToken")
                    self.own(restricted.value)
                    n.check(n.advapi.CreateProcessAsUserW(restricted, str(executable), command, None, None,
                            True, flags, environment, str(root / "worker"), c.byref(startup), c.byref(info)), "CreateProcessAsUserW")
                    self.adopt(info)
                finally:
                    release_failed = bool(restricting_sid.value and n.kernel.LocalFree(restricting_sid))
                    for handle in (restricted.value, token):
                        if handle:
                            try:
                                self.close_handle(handle)
                            except WindowsErrorCode:
                                release_failed = True
                    if release_failed:
                        raise WindowsErrorCode("ROLLBACK_INCOMPLETE", 0)
            else:
                n.check(n.kernel.CreateProcessW(str(executable), command, None, None, True, flags,
                                                environment, str(root / "worker"), c.byref(startup), c.byref(info)), "CreateProcessW")
                self.adopt(info)
            # Every failure through this point leaves the process suspended.
            n.check(n.kernel.AssignProcessToJobObject(job, self.process), "AssignProcessToJobObject")
            self.assigned = True
            member = w.BOOL()
            n.check(n.kernel.IsProcessInJob(self.process, job, c.byref(member)), "IsProcessInJob")
            if not member.value:
                raise WindowsErrorCode("JOB_MEMBERSHIP_MISSING", 0)
            for handle in (child_in, child_out, child_err):
                self.close_handle(handle)
            stdin = self.stream(parent_in, "wb")
            stdout = self.stream(parent_out, "rb")
            stderr = self.stream(parent_err, "rb")
            if n.kernel.ResumeThread(self.thread) != 1:
                raise WindowsErrorCode("ResumeThread")
            self.resumed = True
            self.close_handle(self.thread)
            self.thread = None
            return stdin, stdout, stderr
        finally:
            n.kernel.DeleteProcThreadAttributeList(attribute_buffer)

    def cleanup(self):
        failures = []
        if self.process:
            try:
                state = self.native.kernel.WaitForSingleObject(self.process, 0)
                if state == 258 and not self.assigned:
                    terminated = self.native.kernel.TerminateProcess(self.process, 125)
                    # Job termination can race this partial-launch cleanup.
                    # Accept an already-dying process only after its handle signals.
                    if not terminated and self.native.kernel.WaitForSingleObject(self.process, 3000) != 0:
                        raise WindowsErrorCode("TerminateProcess")
                elif state not in (0, 258):
                    raise WindowsErrorCode("WaitProcess")
                if self.native.kernel.WaitForSingleObject(self.process, 3000) != 0:
                    raise WindowsErrorCode("WaitProcessCleanup")
                exit_code = w.DWORD()
                self.native.check(self.native.kernel.GetExitCodeProcess(self.process, c.byref(exit_code)), "GetExitCodeProcess")
                self.exit_code = exit_code.value
                if self.resources is not None:
                    self.resources.observe_process()
            except WindowsErrorCode as exc:
                failures.append(exc.api)
        for stream in self.streams:
            try:
                stream.close()
            except OSError:
                failures.append("CloseStream")
                if self.resources is not None:
                    self.resources.errors.add("CloseStream")
        for handle in list(reversed(self.handles)):
            try:
                self.close_handle(handle)
            except WindowsErrorCode as exc:
                failures.append(exc.api)
        if self.resources is not None:
            self.resources.handles_released()
        return failures


class PocEnvironment:
    """Exclusive temporary tree. DACL changes are confined to this owned tree."""
    def __init__(self):
        self.native = Native()
        self.directory = None
        self.root = None
        self.sid = c.c_void_p()
        self.cleanup_state = "NOT_VERIFIED"
        self._native_cleanup_failed = False
        self._run_lock = threading.Lock()

    def __enter__(self):
        self.discovery = self.native.discovery()
        self.directory = tempfile.TemporaryDirectory(prefix="cryptolab-isolation-poc-")
        self.root = Path(self.directory.name).resolve()
        try:
            hr = self.native.userenv.DeriveAppContainerSidFromAppContainerName(
                "CryptoLab.PoC." + uuid.uuid4().hex, c.byref(self.sid))
            if hr != 0:
                raise WindowsErrorCode("DeriveAppContainerSid", hr & 0xffffffff)
            # Derive a SID only. No AppContainer profile/account/registry entry is created.
            for name in ("protected", "allowed", "worker", "outputs"):
                (self.root / name).mkdir()
            self._stage_runtime()
            self._secure_tree()
            self.cleanup_state = "ACTIVE"
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def _stage_runtime(self):
        base = Path(sys.base_prefix)
        worker = self.root / "worker"
        version = f"python{sys.version_info.major}{sys.version_info.minor}"
        # The GUI-subsystem interpreter avoids a separate console host in the Job.
        shutil.copyfile(base / "pythonw.exe", worker / "pythonw.exe")
        for source in base.glob("*.dll"):
            shutil.copyfile(source, worker / source.name)
        shutil.copytree(base / "DLLs", worker / "DLLs", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Stage stdlib only. The runtime never imports site-packages or project modules.
        with zipfile.ZipFile(worker / f"{version}.zip", "w", zipfile.ZIP_STORED) as archive:
            for directory, directories, files in os.walk(base / "Lib"):
                directories[:] = [name for name in directories if name not in
                                   {"site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter", "ensurepip"}]
                for name in files:
                    if name.endswith(".py"):
                        source = Path(directory) / name
                        archive.write(source, source.relative_to(base / "Lib").as_posix())
        (worker / f"{version}._pth").write_text(f"{version}.zip\nDLLs\n.\n", encoding="ascii")
        for name in ("isolation_probe.py", "mock_worker.py"):
            shutil.copyfile(Path(__file__).with_name(name), worker / name)
        (self.root / "allowed/context.json").write_bytes(b'{"synthetic":true}')
        # Only this fixed synthetic tree is accepted by the probes.
        fixtures = {"fake_exchange_key.txt": b"FAKE_EXCHANGE_API_KEY",
                    "fake_private_token.txt": b"FAKE_PRIVATE_TOKEN",
                    "fake_user_secret.env": b"FAKE_SECRET_CANARY"}
        for name, value in fixtures.items():
            (self.root / "protected" / name).write_bytes(value)
        database = sqlite3.connect(self.root / "protected/fake_ledger.sqlite3")
        try:
            database.execute("CREATE TABLE synthetic_canary(value TEXT NOT NULL)")
            database.execute("INSERT INTO synthetic_canary VALUES ('FAKE_LEDGER_CANARY')")
            database.commit()
        finally:
            database.close()
        fixtures["fake_ledger.sqlite3"] = (self.root / "protected/fake_ledger.sqlite3").read_bytes()
        self.originals = fixtures

    def _secure_tree(self):
        token = self.native.current_token()
        try:
            user_info = self.native.token_info(token, 1)
            user_sid = c.cast(user_info, c.POINTER(SID_AND_ATTRIBUTES)).contents.Sid
            user = self.native.sid_text(user_sid)
        finally:
            self.native.close(token)
        package = self.native.sid_text(self.sid)
        allowed = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{user})(A;OICI;GRGX;;;{package})(A;OICI;GRGX;;;RC)"
        protected = f"D:P(D;OICI;FA;;;{package})(D;OICI;FA;;;RC)(A;OICI;FA;;;SY)(A;OICI;FA;;;{user})"
        self.initial_security = {}
        paths = (self.root, *self.root.rglob("*"))
        for path in paths:
            # Root and every descendant were created exclusively by this instance.
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise EvidenceError("POC_PATH_INVALID")
            self.initial_security[path.relative_to(self.root).as_posix()] = bytes(self.native.file_security(path))
        for path in paths:
            self.native.apply_dacl(path, protected if "protected" in path.relative_to(self.root).parts else allowed)

    def __exit__(self, kind, value, traceback):
        failures = ["PriorNativeCleanupFailure"] if self._native_cleanup_failed else []
        if self.sid.value:
            if self.native.advapi.FreeSid(self.sid):
                failures.append("FreeSid")
            self.sid = c.c_void_p()
        if self.directory is not None:
            try:
                self.directory.cleanup()
                if self.root.exists():
                    failures.append("TemporaryDirectoryExists")
            except OSError:
                failures.append("TemporaryDirectoryCleanup")
        self.cleanup_state = "ROLLBACK_INCOMPLETE" if failures else "COMPLETE"
        if failures:
            raise EvidenceError("ROLLBACK_INCOMPLETE") from None

    def run(self, operation, raw=b"{}", policy=None, cancel=None):
        if type(operation) is not str or operation not in PROBES:
            raise EvidenceError("POC_OPERATION_INVALID")
        policy = policy or IsolationPolicy()
        if self._native_cleanup_failed:
            raise EvidenceError("ROLLBACK_INCOMPLETE")
        if type(policy) is not IsolationPolicy or self.root is None or self.cleanup_state != "ACTIVE":
            raise EvidenceError("POC_STATE_INVALID")
        if type(raw) is not bytes or len(raw) > policy.max_input_bytes:
            raise EvidenceError("POC_INPUT_LIMIT")
        if not self._run_lock.acquire(blocking=False):
            raise EvidenceError("POC_CONCURRENCY_LIMIT")
        try:
            result = self._run(operation, raw, policy, cancel or threading.Event())
            if result["rollback"] == "INCOMPLETE":
                self.cleanup_state = "ROLLBACK_INCOMPLETE"
                self._native_cleanup_failed = True
            return result
        finally:
            self._run_lock.release()

    def _run(self, operation, raw, policy, cancel):
        started = time.monotonic()
        n = self.native
        child = Child(n)
        job = None
        threads = []
        stdout = bytearray()
        observed = {"stdout": 0, "stderr": 0}
        exceeded = threading.Event()
        pipe_error = threading.Event()
        status = "FAILED"
        api_error = None
        code = None
        pids = []
        max_active = 0
        peak = 0
        cleanup = []

        def read(stream, label, target):
            try:
                while True:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    observed[label] += len(chunk)
                    if observed[label] > policy.max_output_bytes:
                        exceeded.set()
                        break
                    if target is not None:
                        target.extend(chunk)
            except OSError:
                pipe_error.set()

        def write(stream):
            try:
                view = memoryview(raw)
                while view:
                    written = stream.write(view)
                    if not written:
                        raise OSError()
                    view = view[written:]
                stream.close()
            except OSError:
                pipe_error.set()

        try:
            if cancel.is_set():
                status = "CANCELLED"
            else:
                job = n.job(policy)
                streams = child.launch(self.root, operation, job, self.sid, policy)
                for function, arguments in ((read, (streams[1], "stdout", stdout)),
                                            (read, (streams[2], "stderr", None)), (write, (streams[0],))):
                    thread = threading.Thread(target=function, args=arguments, daemon=True)
                    thread.start()
                    threads.append(thread)
                deadline = started + policy.timeout_ms / 1000
                while True:
                    current_pids = n.job_pids(job)
                    max_active = max(max_active, n.job_accounting(job).ActiveProcesses)
                    pids = sorted(set(pids) | set(current_pids))
                    peak = max(peak, n.job_limits(job).PeakJobMemoryUsed)
                    state = n.kernel.WaitForSingleObject(child.process, 0)
                    if state not in (0, 258):
                        raise WindowsErrorCode("WaitProcess")
                    if cancel.is_set():
                        status = "CANCELLED"
                        break
                    if exceeded.is_set():
                        status = "OUTPUT_LIMIT"
                        break
                    if time.monotonic() >= deadline:
                        status = "TIMEOUT"
                        break
                    if state == 0 and all(not thread.is_alive() for thread in threads):
                        exit_code = w.DWORD()
                        n.check(n.kernel.GetExitCodeProcess(child.process, c.byref(exit_code)), "GetExitCodeProcess")
                        code = exit_code.value
                        status = "EXITED" if code == 0 and not pipe_error.is_set() else "FAILED"
                        break
                    cancel.wait(0.01)
        except WindowsErrorCode as exc:
            api_error = {"api": exc.api, "winerror": exc.code}
            if exc.api == "ROLLBACK_INCOMPLETE":
                cleanup.append(exc.api)
        except (OSError, ValueError):
            api_error = {"api": "POC_IO", "winerror": 0}
        finally:
            if job:
                try:
                    n.check(n.kernel.TerminateJobObject(job, 124), "TerminateJobObject")
                    deadline = time.monotonic() + 3
                    while n.job_pids(job) and time.monotonic() < deadline:
                        time.sleep(0.01)
                    if n.job_pids(job):
                        cleanup.append("JobProcessesRemain")
                except WindowsErrorCode as exc:
                    cleanup.append(exc.api)
            for thread in threads:
                thread.join(3)
                if thread.is_alive():
                    cleanup.append("PipeThreadAlive")
            cleanup.extend(child.cleanup())
            if job:
                try:
                    n.close(job)
                except WindowsErrorCode as exc:
                    cleanup.append(exc.api)
        return {"status": "ROLLBACK_INCOMPLETE" if cleanup else status, "worker_status": status,
                "exit_code": code if code is not None else child.exit_code, "api_error": api_error,
                "rollback": "INCOMPLETE" if cleanup else "COMPLETE",
                "cleanup_errors": cleanup, "job_members_observed": len(pids), "peak_job_bytes": peak,
                "max_active_job_processes": max_active,
                "job_configured": job is not None, "assigned_before_resume": child.assigned,
                "resumed": child.resumed,
                "policy": asdict(policy), "policy_hash": policy.content_hash,
                "stdout_bytes": observed["stdout"], "stderr_bytes": observed["stderr"],
                "stdout": bytes(stdout), "elapsed_ms": int((time.monotonic() - started) * 1000),
                "mode": "ISOLATION_POC"}


def run_suite():
    """Supervisor-owned evidence. Raw worker text never becomes an assurance."""
    from dataclasses import replace
    samples = {}
    with PocEnvironment() as environment:
        discovery = environment.discovery
        policy = IsolationPolicy(identity="JOB_ONLY", timeout_ms=1000)
        samples["normal"] = environment.run("normal", policy=policy)
        samples["memory_denied"] = environment.run("memory", policy=policy)
        samples["memory_control"] = environment.run("memory", policy=replace(
            policy, process_memory_bytes=192 * 1024**2, job_memory_bytes=256 * 1024**2))
        samples["process_denied"] = environment.run("descendant", policy=policy)
        samples["descendants_terminated"] = environment.run("descendant", policy=replace(policy, active_processes=2))
        samples["timeout"] = environment.run("sleep", policy=policy)
        for operation in ("stdout", "stderr"):
            samples[operation] = environment.run(operation, policy=policy)
        for identity in ("RESTRICTED_TOKEN", "APPCONTAINER"):
            samples[identity] = environment.run("filesystem", policy=replace(policy, identity=identity))
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(8)
            port = server.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                connection, _ = server.accept()
                connection.close()
            raw = json.dumps({"port": port}).encode("ascii")
            samples["network_control"] = environment.run("network", raw, policy)
            samples["network_restricted"] = environment.run("network", raw, replace(policy, identity="APPCONTAINER"))
        unmodified = all((environment.root / "protected" / name).read_bytes() == content
                         for name, content in environment.originals.items())
    complete = environment.cleanup_state == "COMPLETE" and all(sample["rollback"] == "COMPLETE" for sample in samples.values())

    def response(name):
        sample = samples[name]
        if sample["status"] != "EXITED":
            return {}
        try:
            value = strict_json(sample["stdout"])
            return value if type(value) is dict else {}
        except EvidenceError:
            return {}

    memory = (response("memory_denied").get("allocated") is False
              and response("memory_control").get("allocated") is True
              and samples["memory_denied"]["assigned_before_resume"])
    process = (response("process_denied").get("winerror") == 1816
               and samples["descendants_terminated"]["status"] == "TIMEOUT"
               and samples["descendants_terminated"]["rollback"] == "COMPLETE")

    def evidence(name, api, state, test, observation, limitation):
        samples_by_control = {"MEMORY_LIMIT": ("memory_denied", "memory_control"),
                              "PROCESS_LIMIT": ("process_denied", "descendants_terminated"),
                              "FILESYSTEM_DENY": ("RESTRICTED_TOKEN", "APPCONTAINER"),
                              "NETWORK_DENY": ("network_control", "network_restricted"),
                              "ROLLBACK": tuple(samples)}
        return {"control": name, "requested_policy_hashes": sorted({samples[key]["policy_hash"]
                for key in samples_by_control[name]}),
                "api": api, "configuration": "APPLIED_AND_READ_BACK" if name in
                ("MEMORY_LIMIT", "PROCESS_LIMIT") else "SEE_SAMPLES",
                "verification": state, "test": test, "observation": observation,
                "synthetic_only": True, "limitation": limitation,
                "failure_reason": None if state == "ENFORCED_AND_TESTED" else "CRITICAL_BOUNDARY_UNVERIFIED"}

    controls = [
        evidence("MEMORY_LIMIT", "SetInformationJobObject/VirtualAlloc", "ENFORCED_AND_TESTED" if memory else "FAILED",
                 "native-allocation-paired-control", "96 MiB denied at 64 MiB process cap and permitted at 192 MiB",
                 "Bounded commitment test; no proof of universal peak/RSS upper bound"),
        evidence("PROCESS_LIMIT", "SetInformationJobObject/CreateProcessW/TerminateJobObject",
                 "ENFORCED_AND_TESTED" if process else "FAILED", "descendant-paired-control",
                 "Creation denied at one process; two-member Job terminated after timeout",
                 "Fixed benign fixtures; abrupt supervisor exit verified separately by pytest"),
        evidence("FILESYSTEM_DENY", "CreateProcessAsUserW/SECURITY_CAPABILITIES/DACL", "NOT_VERIFIED",
                 "protected-synthetic-file-attempts", "Inspect identity samples for launch/init failures",
                 "Failed startup does not prove a denied file operation"),
        evidence("NETWORK_DENY", "SECURITY_CAPABILITIES", "NOT_VERIFIED", "local-listener-control",
                 "Supervisor and JOB_ONLY control reach local listener; AppContainer launch attempted",
                 "External TCP, DNS, loopback denial and IPC containment remain unverified"),
        evidence("ROLLBACK", "TerminateJobObject/CloseHandle/TemporaryDirectory",
                 "ENFORCED_AND_TESTED" if complete and unmodified else "FAILED", "all-owned-resources",
                 "Job process lists empty, handles closed and temporary tree removed",
                 "Failure injection and supervisor-death tests are recorded separately"),
    ]
    sanitized = {name: {key: value for key, value in sample.items() if key != "stdout"}
                 for name, sample in samples.items()}
    return {"schema_version": 1, "mode": "ISOLATION_POC", "discovery": discovery,
            "controls": controls, "samples": sanitized, "canaries_unmodified": unmodified,
            "directory_cleanup": environment.cleanup_state,
            "readiness": "PARTIAL_POC" if memory and process and complete and unmodified else "NOT_READY"}


def main(argv=None):
    """Discovery by default, synthetic execution only with an explicit option."""
    from .cli import Parser
    parser = Parser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--suite", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.suite:
            result = run_suite()
            print(json.dumps(result, sort_keys=True))
            return 0 if result["readiness"] == "PARTIAL_POC" else 2
        native = Native()
        discovery = native.discovery()
        if not args.run:
            print(json.dumps(discovery, sort_keys=True))
            return 0
        with PocEnvironment() as environment:
            result = environment.run("token")
            result["stdout"] = result["stdout"].decode("utf-8", errors="replace")
        result["directory_cleanup"] = environment.cleanup_state
        print(json.dumps({"discovery": discovery, "probe": result}, sort_keys=True))
        return 0 if result["status"] == "EXITED" else 2
    except EvidenceError as exc:
        print(json.dumps({"status": str(exc), "readiness": "NOT_READY"}))
        return 2
    except WindowsErrorCode as exc:
        print(json.dumps({"status": "FAILED", "api": exc.api, "winerror": exc.code, "readiness": "NOT_READY"}))
        return 2
    except OSError:
        print(json.dumps({"status": "POC_IO_FAILED", "readiness": "NOT_READY"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
