"""Native read-only adapter. Persistent calls have no operational entry point."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path

from .profile_plan import ProfilePolicy
from .windows_native import Native, WindowsErrorCode
from ..evidence.core import EvidenceError


class NativeProfileAdapter:
    synthetic_only = False

    def __init__(self):
        self.native = Native()
        self.policy = ProfilePolicy()
        n = self.native
        n._function(n.userenv, "CreateAppContainerProfile", [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR,
                    c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)], c.c_long)
        n._function(n.userenv, "DeleteAppContainerProfile", [w.LPCWSTR], c.c_long)
        n._function(n.userenv, "GetAppContainerFolderPath", [w.LPCWSTR, c.POINTER(w.LPWSTR)], c.c_long)
        self.ole = c.WinDLL("ole32", use_last_error=True)
        n._function(self.ole, "CoTaskMemFree", [c.c_void_p], None)

    def inspect_profile(self):
        import winreg
        n = self.native
        sid, folder = c.c_void_p(), w.LPWSTR()
        hr = n.userenv.DeriveAppContainerSidFromAppContainerName(self.policy.name, c.byref(sid))
        if hr != 0:
            raise WindowsErrorCode("DeriveProfileSid", hr & 0xffffffff)
        try:
            text = n.sid_text(sid)
            hr = n.userenv.GetAppContainerFolderPath(text, c.byref(folder))
            if (hr & 0xffffffff) not in (0, 0x80070002, 0x80070003):
                raise WindowsErrorCode("GetAppContainerFolderPath", hr & 0xffffffff)
            exists = bool(hr == 0 and folder.value and Path(folder.value).exists())
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
            if n.advapi.FreeSid(sid):
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

    def verify_removal(self):
        return {**self.inspect_profile(), "removal_verification": "NOT_VERIFIED"}
