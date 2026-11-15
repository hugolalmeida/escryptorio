"""Fixed benign fixtures. Receives synthetic inputs only and never emits canaries."""
import ctypes as c
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def main():
    operation = sys.argv[1]
    payload = json.loads(sys.stdin.buffer.read(65537))
    result = {}
    if operation == "normal":
        result = {"ok": True, "canary_environment_absent": "FAKE_PRIVATE_TOKEN" not in os.environ,
                  "runtime_executable": Path(sys.executable).name,
                  "runtime_executable_exists": Path(sys.executable).is_file()}
    elif operation == "token":
        from ctypes import wintypes as w
        kernel = c.WinDLL("kernel32", use_last_error=True)
        advapi = c.WinDLL("advapi32", use_last_error=True)
        kernel.GetCurrentProcess.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
        advapi.GetTokenInformation.argtypes = [w.HANDLE, c.c_int, w.LPVOID, w.DWORD, c.POINTER(w.DWORD)]
        token = w.HANDLE()
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)):
            raise RuntimeError("TOKEN_QUERY_FAILED")
        try:
            value, length = w.DWORD(), w.DWORD()
            if not advapi.GetTokenInformation(token, 29, c.byref(value), 4, c.byref(length)):
                raise RuntimeError("TOKEN_QUERY_FAILED")
            result = {"appcontainer": bool(value.value)}
        finally:
            if not kernel.CloseHandle(token):
                raise RuntimeError("TOKEN_CLOSE_FAILED")
    elif operation == "memory":
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.VirtualAlloc.argtypes = [c.c_void_p, c.c_size_t, c.c_ulong, c.c_ulong]
        kernel.VirtualAlloc.restype = c.c_void_p
        kernel.VirtualFree.argtypes = [c.c_void_p, c.c_size_t, c.c_ulong]
        kernel.VirtualFree.restype = c.c_int
        # Bounded native commitment, without touching pages or exhausting host RAM.
        address = kernel.VirtualAlloc(None, 96 * 1024 * 1024, 0x3000, 4)
        error = c.get_last_error() if not address else 0
        if address and not kernel.VirtualFree(address, 0, 0x8000):
            raise RuntimeError("MEMORY_RELEASE_FAILED")
        result = {"allocation_bytes": 96 * 1024 * 1024, "allocated": bool(address), "winerror": error}
    elif operation == "filesystem":
        root = Path.cwd().parent
        allowed = root / "allowed" / "context.json"
        result["allowed_read"] = allowed.read_bytes() == b'{"synthetic":true}'
        targets = ("fake_exchange_key.txt", "fake_private_token.txt", "fake_ledger.sqlite3", "fake_user_secret.env")
        for index, name in enumerate(targets):
            for action in ("read", "write"):
                try:
                    with (root / "protected" / name).open("rb" if action == "read" else "r+b") as handle:
                        if action == "read":
                            handle.read(1)
                        else:
                            handle.write(b"x")
                    result[f"{index}_{action}"] = 0
                except OSError as exc:
                    result[f"{index}_{action}"] = exc.winerror
        for label, path in (("absolute", root / "protected" / targets[0]),
                            ("relative", Path("../protected") / targets[0])):
            try:
                path.read_bytes()
                result[label] = 0
            except OSError as exc:
                result[label] = exc.winerror
        try:
            list((root / "protected").iterdir())
            result["list"] = 0
        except OSError as exc:
            result["list"] = exc.winerror
    elif operation == "network":
        # Both destinations are local synthetic listeners supplied by supervisor.
        for label, address in (("loopback", "127.0.0.1"), ("tcp_local", "127.0.0.1")):
            with socket.socket() as connection:
                connection.settimeout(0.5)
                try:
                    connection.connect((address, payload["port"]))
                    result[label] = 0
                except OSError as exc:
                    result[label] = exc.winerror
    elif operation == "descendant":
        try:
            child = subprocess.Popen([sys.executable, "-I", "-S", "-c", "import time; time.sleep(20)"],
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            result = {"spawned": True}
            # Parent fixture remains alive so the supervisor can query Job membership.
            print(json.dumps(result), flush=True)
            time.sleep(20)
            child.wait()
            return
        except OSError as exc:
            result = {"spawned": False, "winerror": exc.winerror}
    elif operation == "sleep":
        time.sleep(20)
    elif operation in ("stdout", "stderr"):
        stream = sys.stdout if operation == "stdout" else sys.stderr
        stream.write("x" * 131072)
        stream.flush()
    elif operation == "invalid_json":
        print("{")
        return
    elif operation == "forged_security":
        result = {"security": "ENFORCED_AND_TESTED"}
    elif operation == "exit":
        sys.exit(7)
    else:
        raise ValueError("PROBE_UNSUPPORTED")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
