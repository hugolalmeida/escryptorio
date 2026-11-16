"""Small x64 Win32 boundary. All objects are anonymous or caller-owned."""
import ctypes as c
import os
from ctypes import wintypes as w


class WindowsErrorCode(Exception):
    def __init__(self, api, code=None):
        self.api = api
        self.code = c.get_last_error() if code is None else code
        super().__init__(f"{api}:{self.code}")


class IO_COUNTERS(c.Structure):
    _fields_ = [(name, c.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class BASIC_LIMIT(c.Structure):
    _fields_ = [("PerProcessUserTimeLimit", c.c_int64), ("PerJobUserTimeLimit", c.c_int64),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", c.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]


class EXTENDED_LIMIT(c.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t)]


class ACCOUNTING(c.Structure):
    _fields_ = [(name, c.c_int64) for name in ("TotalUserTime", "TotalKernelTime",
                "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")] + [
                (name, w.DWORD) for name in ("TotalPageFaultCount", "TotalProcesses",
                                           "ActiveProcesses", "TotalTerminatedProcesses")]


class STARTUPINFO(c.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
                ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
                ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
                ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", c.c_void_p), ("hStdInput", w.HANDLE),
                ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class STARTUPINFOEX(c.Structure):
    _fields_ = [("StartupInfo", STARTUPINFO), ("lpAttributeList", c.c_void_p)]


class PROCESS_INFORMATION(c.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class SECURITY_ATTRIBUTES(c.Structure):
    _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", c.c_void_p), ("bInheritHandle", w.BOOL)]


class SECURITY_CAPABILITIES(c.Structure):
    _fields_ = [("AppContainerSid", c.c_void_p), ("Capabilities", c.c_void_p),
                ("CapabilityCount", w.DWORD), ("Reserved", w.DWORD)]


class SID_AND_ATTRIBUTES(c.Structure):
    _fields_ = [("Sid", c.c_void_p), ("Attributes", w.DWORD)]


class BY_HANDLE_FILE_INFORMATION(c.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME),
                ("accessed", w.FILETIME), ("written", w.FILETIME),
                ("volume", w.DWORD), ("size_high", w.DWORD), ("size_low", w.DWORD),
                ("links", w.DWORD), ("index_high", w.DWORD), ("index_low", w.DWORD)]


class FILE_ID_INFO(c.Structure):
    _fields_ = [("volume", c.c_uint64), ("identifier", c.c_ubyte * 16)]


class Native:
    def __init__(self):
        if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
            raise WindowsErrorCode("WINDOWS_X64_REQUIRED", 0)
        for structure, size in ((BASIC_LIMIT, 64), (EXTENDED_LIMIT, 144), (STARTUPINFO, 104),
                                (STARTUPINFOEX, 112), (PROCESS_INFORMATION, 24),
                                (SECURITY_ATTRIBUTES, 24), (SECURITY_CAPABILITIES, 24),
                                (ACCOUNTING, 48), (SID_AND_ATTRIBUTES, 16), (IO_COUNTERS, 48),
                                (BY_HANDLE_FILE_INFORMATION, 52), (FILE_ID_INFO, 24)):
            if c.sizeof(structure) != size:
                raise WindowsErrorCode("STRUCTURE_SIZE_INVALID", 0)
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.advapi = c.WinDLL("advapi32", use_last_error=True)
        self.userenv = c.WinDLL("userenv", use_last_error=True)
        self._bind()

    def _bind(self):
        pointer = c.c_void_p
        handle_pointer = c.POINTER(w.HANDLE)
        self._function(self.kernel, "GetCurrentProcess", [], w.HANDLE)
        self._function(self.kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        self._function(self.kernel, "LocalFree", [pointer], pointer)
        self._function(self.kernel, "GetFileAttributesW", [w.LPCWSTR], w.DWORD)
        self._function(self.kernel, "GetDriveTypeW", [w.LPCWSTR], w.UINT)
        self._function(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD, w.DWORD, pointer,
                       w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        self._function(self.kernel, "GetFileInformationByHandle", [w.HANDLE, c.POINTER(BY_HANDLE_FILE_INFORMATION)], w.BOOL)
        self._function(self.kernel, "GetFileInformationByHandleEx", [w.HANDLE, c.c_int, pointer, w.DWORD], w.BOOL)
        self._function(self.kernel, "GetFinalPathNameByHandleW", [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD)
        self._function(self.kernel, "GetHandleInformation", [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.advapi, "GetKernelObjectSecurity", [w.HANDLE, w.DWORD, pointer, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.kernel, "CreateJobObjectW", [pointer, w.LPCWSTR], w.HANDLE)
        self._function(self.kernel, "SetInformationJobObject", [w.HANDLE, c.c_int, pointer, w.DWORD], w.BOOL)
        self._function(self.kernel, "QueryInformationJobObject", [w.HANDLE, c.c_int, pointer, w.DWORD, pointer], w.BOOL)
        self._function(self.kernel, "AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL)
        self._function(self.kernel, "IsProcessInJob", [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)], w.BOOL)
        self._function(self.kernel, "TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL)
        self._function(self.kernel, "TerminateProcess", [w.HANDLE, w.UINT], w.BOOL)
        self._function(self.kernel, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
        self._function(self.kernel, "GetExitCodeProcess", [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.kernel, "ResumeThread", [w.HANDLE], w.DWORD)
        self._function(self.kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        self._function(self.kernel, "GetProcessHandleCount", [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.kernel, "CreatePipe", [handle_pointer, handle_pointer, pointer, w.DWORD], w.BOOL)
        self._function(self.kernel, "SetHandleInformation", [w.HANDLE, w.DWORD, w.DWORD], w.BOOL)
        self._function(self.kernel, "InitializeProcThreadAttributeList", [pointer, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)], w.BOOL)
        self._function(self.kernel, "UpdateProcThreadAttribute", [pointer, w.DWORD, c.c_size_t, pointer, c.c_size_t, pointer, pointer], w.BOOL)
        self._function(self.kernel, "DeleteProcThreadAttributeList", [pointer], None)
        self._function(self.kernel, "CreateProcessW", [w.LPCWSTR, w.LPWSTR, pointer, pointer, w.BOOL,
                       w.DWORD, pointer, w.LPCWSTR, pointer, c.POINTER(PROCESS_INFORMATION)], w.BOOL)
        self._function(self.advapi, "CreateProcessAsUserW", [w.HANDLE, w.LPCWSTR, w.LPWSTR, pointer,
                       pointer, w.BOOL, w.DWORD, pointer, w.LPCWSTR, pointer,
                       c.POINTER(PROCESS_INFORMATION)], w.BOOL)
        self._function(self.advapi, "OpenProcessToken", [w.HANDLE, w.DWORD, handle_pointer], w.BOOL)
        self._function(self.advapi, "GetTokenInformation", [w.HANDLE, c.c_int, pointer, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.advapi, "CreateRestrictedToken", [w.HANDLE, w.DWORD, w.DWORD, pointer,
                       w.DWORD, pointer, w.DWORD, pointer, handle_pointer], w.BOOL)
        self._function(self.advapi, "ConvertSidToStringSidW", [pointer, c.POINTER(w.LPWSTR)], w.BOOL)
        self._function(self.advapi, "ConvertStringSidToSidW", [w.LPCWSTR, c.POINTER(pointer)], w.BOOL)
        self._function(self.advapi, "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                       [w.LPCWSTR, w.DWORD, c.POINTER(pointer), pointer], w.BOOL)
        self._function(self.advapi, "SetFileSecurityW", [w.LPCWSTR, w.DWORD, pointer], w.BOOL)
        self._function(self.advapi, "GetFileSecurityW", [w.LPCWSTR, w.DWORD, pointer, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.advapi, "GetSecurityDescriptorDacl", [pointer, c.POINTER(w.BOOL), c.POINTER(pointer), c.POINTER(w.BOOL)], w.BOOL)
        self._function(self.advapi, "GetSecurityDescriptorOwner", [pointer, c.POINTER(pointer), c.POINTER(w.BOOL)], w.BOOL)
        self._function(self.advapi, "GetSecurityDescriptorControl", [pointer, c.POINTER(w.WORD), c.POINTER(w.DWORD)], w.BOOL)
        self._function(self.userenv, "DeriveAppContainerSidFromAppContainerName", [w.LPCWSTR, c.POINTER(pointer)], c.c_long)
        self._function(self.advapi, "FreeSid", [pointer], pointer)

    @staticmethod
    def _function(dll, name, arguments, result):
        function = getattr(dll, name)
        function.argtypes = arguments
        function.restype = result

    @staticmethod
    def check(value, api):
        if not value:
            raise WindowsErrorCode(api)
        return value

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise WindowsErrorCode("ROLLBACK_INCOMPLETE")

    def token_info(self, token, kind):
        length = w.DWORD()
        buffer = c.create_string_buffer(4 if kind in (8, 18, 20, 29) else 4096)
        result = self.advapi.GetTokenInformation(token, kind, buffer, len(buffer), c.byref(length))
        if not result:
            if c.get_last_error() != 122 or not 4096 < length.value <= 65536:
                raise WindowsErrorCode("GetTokenInformation")
            buffer = c.create_string_buffer(length.value)
            self.check(self.advapi.GetTokenInformation(token, kind, buffer, len(buffer), c.byref(length)), "GetTokenInformation")
        return buffer

    def current_token(self):
        token = w.HANDLE()
        self.check(self.advapi.OpenProcessToken(self.kernel.GetCurrentProcess(), 0xB, c.byref(token)), "OpenProcessToken")
        return token.value

    def sid_text(self, sid):
        text = w.LPWSTR()
        self.check(self.advapi.ConvertSidToStringSidW(sid, c.byref(text)), "ConvertSidToStringSidW")
        try:
            return text.value
        finally:
            if self.kernel.LocalFree(c.cast(text, c.c_void_p)):
                raise WindowsErrorCode("ROLLBACK_INCOMPLETE")

    def file_security(self, path, information=4):
        length = w.DWORD()
        result = self.advapi.GetFileSecurityW(str(path), information, None, 0, c.byref(length))
        if result or c.get_last_error() != 122 or not 0 < length.value <= 65536:
            raise WindowsErrorCode("GetFileSecuritySize")
        buffer = c.create_string_buffer(length.value)
        self.check(self.advapi.GetFileSecurityW(str(path), information, buffer, len(buffer), c.byref(length)), "GetFileSecurityW")
        return buffer

    def security_owner_control(self, descriptor):
        owner, defaulted, control, revision = c.c_void_p(), w.BOOL(), w.WORD(), w.DWORD()
        self.check(self.advapi.GetSecurityDescriptorOwner(descriptor, c.byref(owner), c.byref(defaulted)), "GetSecurityDescriptorOwner")
        self.check(self.advapi.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)), "GetSecurityDescriptorControl")
        if not owner.value or defaulted.value:
            raise WindowsErrorCode("JOURNAL_SECURITY_NOT_VERIFIED", 0)
        return self.sid_text(owner), control.value

    def metadata_handle(self, path, *, directory, allow_delete=False):
        # OPEN_EXISTING; GENERIC_READ also participates in sharing checks.
        # Metadata-only access does NOT exclude concurrent data writers.
        # Directories deny delete sharing. Files deny write and, normally, delete.
        sharing = 3 if directory else (5 if allow_delete else 1)
        handle = self.kernel.CreateFileW(str(path), 0x80020080, sharing, None, 3,
                                         0x02200000, None)  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        if handle == c.c_void_p(-1).value or handle is None:
            raise WindowsErrorCode("CreateFileMetadata")
        return handle

    def file_handle_info(self, handle):
        basic, identity = BY_HANDLE_FILE_INFORMATION(), FILE_ID_INFO()
        self.check(self.kernel.GetFileInformationByHandle(handle, c.byref(basic)), "GetFileInformationByHandle")
        self.check(self.kernel.GetFileInformationByHandleEx(handle, 18, c.byref(identity), c.sizeof(identity)), "GetFileInformationByHandleEx")
        return (identity.volume, bytes(identity.identifier)), basic.attributes, basic.links

    def final_path(self, handle):
        buffer = c.create_unicode_buffer(512)
        length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if length >= len(buffer):
            if length > 32767:
                raise WindowsErrorCode("FINAL_PATH_LIMIT", 0)
            buffer = c.create_unicode_buffer(length + 1)
            length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise WindowsErrorCode("GetFinalPathNameByHandleW")
        return buffer.value

    def handle_security(self, handle):
        length = w.DWORD()
        result = self.advapi.GetKernelObjectSecurity(handle, 5, None, 0, c.byref(length))
        if result or c.get_last_error() != 122 or not 0 < length.value <= 65536:
            raise WindowsErrorCode("GetKernelObjectSecuritySize")
        buffer = c.create_string_buffer(length.value)
        self.check(self.advapi.GetKernelObjectSecurity(handle, 5, buffer, len(buffer), c.byref(length)), "GetKernelObjectSecurity")
        return buffer

    def dacl_bytes(self, descriptor):
        present, defaulted, acl = w.BOOL(), w.BOOL(), c.c_void_p()
        self.check(self.advapi.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)), "GetSecurityDescriptorDacl")
        if not present.value or not acl.value:
            raise WindowsErrorCode("DACL_MISSING", 0)
        size = c.c_ushort.from_address(acl.value + 2).value
        if size < 8:
            raise WindowsErrorCode("DACL_INVALID", 0)
        raw = c.string_at(acl, size)
        count = int.from_bytes(raw[4:6], "little")
        entries, offset = [], 8
        for _ in range(count):
            length = int.from_bytes(raw[offset+2:offset+4], "little")
            if length < 8 or offset + length > size:
                raise WindowsErrorCode("DACL_INVALID", 0)
            mask = int.from_bytes(raw[offset+4:offset+8], "little")
            mapped = mask & 0x0fffffff
            for bit, rights in ((0x80000000, 0x120089), (0x40000000, 0x120116),
                                (0x20000000, 0x1200a0), (0x10000000, 0x1f01ff)):
                if mask & bit:
                    mapped |= rights
            entries.append((raw[offset:offset+2], mapped, raw[offset+8:offset+length]))
            offset += length
        return entries

    def apply_dacl(self, path, sddl):
        descriptor = c.c_void_p()
        self.check(self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, c.byref(descriptor), None), "ConvertSecurityDescriptor")
        try:
            self.check(self.advapi.SetFileSecurityW(str(path), 0x80000004, descriptor), "SetFileSecurityW")
            if self.dacl_bytes(descriptor) != self.dacl_bytes(self.file_security(path)):
                raise WindowsErrorCode("DACL_READBACK_MISMATCH", 0)
        finally:
            if self.kernel.LocalFree(descriptor):
                raise WindowsErrorCode("ROLLBACK_INCOMPLETE")

    def job(self, policy):
        handle = self.check(self.kernel.CreateJobObjectW(None, None), "CreateJobObjectW")
        try:
            limits = EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100 | 0x200 | 0x8
            limits.BasicLimitInformation.ActiveProcessLimit = policy.active_processes
            limits.ProcessMemoryLimit = policy.process_memory_bytes
            limits.JobMemoryLimit = policy.job_memory_bytes
            self.check(self.kernel.SetInformationJobObject(handle, 9, c.byref(limits), c.sizeof(limits)), "SetInformationJobObject")
            actual = self.job_limits(handle)
            if (actual.BasicLimitInformation.LimitFlags != limits.BasicLimitInformation.LimitFlags
                or actual.BasicLimitInformation.ActiveProcessLimit != policy.active_processes
                or actual.ProcessMemoryLimit != policy.process_memory_bytes
                or actual.JobMemoryLimit != policy.job_memory_bytes):
                raise WindowsErrorCode("JOB_POLICY_MISMATCH", 0)
            return handle
        except BaseException:
            try:
                self.close(handle)
            except WindowsErrorCode:
                raise WindowsErrorCode("ROLLBACK_INCOMPLETE", 0) from None
            raise

    def job_limits(self, handle):
        limits = EXTENDED_LIMIT()
        self.check(self.kernel.QueryInformationJobObject(handle, 9, c.byref(limits), c.sizeof(limits), None), "QueryJobLimits")
        return limits

    def job_pids(self, handle):
        # Policy permits at most two processes. The fixed buffer has room for 32.
        buffer = c.create_string_buffer(8 + 32 * 8)
        self.check(self.kernel.QueryInformationJobObject(handle, 3, buffer, len(buffer), None), "QueryJobProcessIds")
        count = w.DWORD.from_buffer(buffer, 4).value
        if count > 32:
            raise WindowsErrorCode("JOB_PROCESS_LIST_OVERFLOW", 0)
        return list((c.c_size_t * count).from_buffer(buffer, 8))

    def job_accounting(self, handle):
        result = ACCOUNTING()
        self.check(self.kernel.QueryInformationJobObject(handle, 1, c.byref(result),
                                                        c.sizeof(result), None), "QueryJobAccounting")
        return result

    def handle_count(self):
        count = w.DWORD()
        self.check(self.kernel.GetProcessHandleCount(self.kernel.GetCurrentProcess(), c.byref(count)), "GetProcessHandleCount")
        return count.value

    def discovery(self):
        token = self.current_token()
        restricted = w.HANDLE()
        try:
            result = {"token_type": w.DWORD.from_buffer(self.token_info(token, 8)).value,
                      "elevated": bool(w.DWORD.from_buffer(self.token_info(token, 20)).value),
                      "elevation_type": w.DWORD.from_buffer(self.token_info(token, 18)).value,
                      "appcontainer": bool(w.DWORD.from_buffer(self.token_info(token, 29)).value),
                      "pointer_bytes": c.sizeof(c.c_void_p)}
            privileges = self.token_info(token, 3)
            count = w.DWORD.from_buffer(privileges).value
            result["privileges_present"] = count
            result["privileges_enabled"] = sum(bool(w.DWORD.from_buffer(privileges, 4 + i * 12 + 8).value & 2)
                                               for i in range(count))
            if result["elevated"]:
                raise WindowsErrorCode("NON_ELEVATED_TOKEN_REQUIRED", 0)
            self.check(self.advapi.CreateRestrictedToken(token, 1, 0, None, 0, None, 0, None,
                                                       c.byref(restricted)), "CreateRestrictedToken")
            result["restricted_token_creation"] = "AVAILABLE"
            return result
        finally:
            try:
                if restricted.value:
                    self.close(restricted.value)
            finally:
                self.close(token)
