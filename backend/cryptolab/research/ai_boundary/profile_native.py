"""Native read-only adapter. Persistent calls have no operational entry point."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
from typing import Protocol

from .profile_plan import ProfilePolicy
from .profile_journal import Record
from .windows_native import Native, SID_AND_ATTRIBUTES, WindowsErrorCode
from ..evidence.core import EvidenceError


class NativeProfileAdapter:
    synthetic_only = False

    def __init__(self):
        self.native = Native()
        self.policy = ProfilePolicy()
        n = self.native
        n._function(n.userenv, "CreateAppContainerProfile", [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR,
                    c.POINTER(SID_AND_ATTRIBUTES), w.DWORD, c.POINTER(c.c_void_p)], c.c_long)
        n._function(n.userenv, "DeleteAppContainerProfile", [w.LPCWSTR], c.c_long)
        n._function(n.userenv, "GetAppContainerFolderPath", [w.LPCWSTR, c.POINTER(w.LPWSTR)], c.c_long)
        self.ole = c.WinDLL("ole32", use_last_error=True)
        n._function(self.ole, "CoTaskMemFree", [c.c_void_p], None)

    def inspect_profile(self):
        import winreg
        n = self.native
        sid, folder = c.c_void_p(), w.LPWSTR()
        try:
            hr = n.userenv.DeriveAppContainerSidFromAppContainerName(self.policy.name, c.byref(sid))
            if hr != 0 or not sid.value:
                raise WindowsErrorCode("DeriveProfileSid", hr & 0xffffffff)
            text = n.sid_text(sid)
            hr = n.userenv.GetAppContainerFolderPath(text, c.byref(folder))
            if (hr & 0xffffffff) not in (0, 0x80070002, 0x80070003):
                raise WindowsErrorCode("GetAppContainerFolderPath", hr & 0xffffffff)
            if hr == 0 and not folder.value:
                raise WindowsErrorCode("GetAppContainerFolderPath_NULL", 0)
            exists = False
            if hr == 0:
                # stat propagates access errors; exists() can hide them as absence.
                folder_path = Path(folder.value)
                if not folder_path.is_absolute():
                    raise WindowsErrorCode("GetAppContainerFolderPath_INVALID", 0)
                try:
                    folder_path.lstat()
                    exists = True
                except FileNotFoundError:
                    pass
            key = "Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\" + text
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ):
                    mapped = True
            except FileNotFoundError:
                mapped = False
            return {"profile_name": self.policy.name, "expected_sid": text,
                    "folder_present": exists, "mapping_present": mapped,
                    "status": "PROFILE_ALREADY_EXISTS" if exists or mapped else "ABSENT_IN_INSPECTED_LOCATIONS"}
        finally:
            if folder:
                self.ole.CoTaskMemFree(c.cast(folder, c.c_void_p))
            if sid.value and n.advapi.FreeSid(sid):
                raise WindowsErrorCode("ROLLBACK_INCOMPLETE")

    def prepare_creation(self):
        result = self.inspect_profile()
        if result["status"] == "PROFILE_ALREADY_EXISTS":
            raise EvidenceError("PROFILE_ALREADY_EXISTS")
        return {**result, "authorization": "PROFILE_CREATION_REQUIRES_APPROVAL"}

    def create_profile(self):
        raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")

    def delete_profile(self):
        raise EvidenceError("PROFILE_DELETION_REQUIRES_APPROVAL")

    def verify_profile(self):
        return self.inspect_profile()

    def verify_removal(self, journal, resources):
        from .rollback_verification import verify_removal
        return verify_removal(journal, resources, self)


class ProfileOperationPort(Protocol):
    """Future supervisor port; deliberately no implementation using native DLLs.

    Ownership combines a live S_OK Create receipt with the durable operation;
    neither name, derived SID nor a recovery journal can reconstruct that receipt.
    The next reviewed bridge must also collect handle/Job/storage observations.
    """
    def create_owned(self, operation: Record) -> str: ...
    def delete_owned(self, operation: Record) -> None: ...


class PreparedNativeMutationContract:
    """Exact Win32 call bodies disconnected from the native adapter.

    Only a synthetic API object can construct this test seam. A future reviewed
    operational bridge is required before using these bodies with userenv.dll.
    """
    synthetic_only = True

    def __init__(self, api, expected_sid: str):
        if getattr(api, "synthetic_only", False) is not True:
            raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")
        # Reuse the strict SID grammar; no optional/implicit expected identity.
        Record(operation_id="0" * 64, policy_id=ProfilePolicy().policy_id,
               ownership_token="0" * 64, expected_sid=expected_sid,
               created_at_ms=0, last_transition_ms=0)
        self.api = api
        self.expected_sid = expected_sid
        self.owned_sid = None

    def lookup(self, name):
        if name != ProfilePolicy().name:
            raise EvidenceError("PROFILE_IDENTITY_INVALID")
        return self.api.lookup(name)

    def create(self, name, capabilities):
        if name != ProfilePolicy().name or capabilities != ():
            raise EvidenceError("PROFILE_POLICY_INVALID")
        if self.lookup(name) is not None:
            raise EvidenceError("PROFILE_ALREADY_EXISTS")
        sid = c.c_void_p()
        try:
            hr = self.api.CreateAppContainerProfile(name, name, "Escryptorio synthetic isolation test",
                                                    None, 0, c.byref(sid))
            if (hr & 0xffffffff) == 0x800700b7:
                raise EvidenceError("PROFILE_ALREADY_EXISTS")
            if hr != 0 or not sid.value:
                raise WindowsErrorCode("CreateAppContainerProfile", hr & 0xffffffff)
            text = self.api.sid_text(sid)
            if text != self.expected_sid or self.lookup(name) != text:
                raise EvidenceError("ROLLBACK_REQUIRES_MANUAL_REVIEW")
            self.owned_sid = text
            return text
        finally:
            if sid.value and self.api.FreeSid(sid):
                raise EvidenceError("ROLLBACK_INCOMPLETE")

    def stop_and_release(self):
        self.api.stop_and_release()

    def inspect_profile(self):
        return self.api.inspect_profile()

    def delete(self, name):
        if name != ProfilePolicy().name or self.owned_sid is None or self.lookup(name) != self.owned_sid:
            raise EvidenceError("ROLLBACK_REQUIRES_MANUAL_REVIEW")
        hr = self.api.DeleteAppContainerProfile(name)
        if hr != 0:
            raise WindowsErrorCode("DeleteAppContainerProfile", hr & 0xffffffff)
        if self.lookup(name) is not None or self.api.verify_storage_absent(name) is not True:
            raise EvidenceError("ROLLBACK_INCOMPLETE")
        self.owned_sid = None
