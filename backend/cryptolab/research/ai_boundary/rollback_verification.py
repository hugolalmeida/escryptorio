"""Independent read-only checks. Observations never authorize profile deletion."""
from typing import Literal

from .contracts import Closed, Hash
from .profile_plan import PROFILE_NAME, ProfilePolicy
from .windows_native import WindowsErrorCode
from ..evidence.core import EvidenceError

Status = Literal["PROFILE_ABSENT_IN_CHECKED_LOCATIONS", "PROFILE_PRESENT",
                 "RESIDUAL_RESOURCE_FOUND", "VERIFICATION_UNAVAILABLE", "VERIFICATION_ERROR"]


class ResourceObservations(Closed):
    """Supervisor-owned receipts; worker JSON must never populate this contract."""
    operation_id: Hash
    policy_id: Hash
    ownership_token: Hash
    expected_sid: str
    ownership_confirmed: bool | None = None
    delete_succeeded: bool | None = None
    process_stopped: bool | None = None
    job_empty: bool | None = None
    handles_released: bool | None = None
    operation_directories_absent: bool | None = None
    tree_absent: bool | None = None
    source: Literal["TESTED_MOCK", "SUPERVISOR_READ_ONLY"]


class RemovalResult(Closed):
    schema_version: Literal[1] = 1
    operation_id: Hash
    policy_id: Hash
    ownership_token: Hash
    expected_sid: str
    profile_name: Literal[PROFILE_NAME] = PROFILE_NAME
    status: Status
    source: Literal["TESTED_MOCK", "SUPERVISOR_READ_ONLY"]
    scope: Literal["EXACT_MAPPING_API_STORAGE_AND_OPERATION_RESOURCES"] = "EXACT_MAPPING_API_STORAGE_AND_OPERATION_RESOURCES"
    details: tuple[str, ...] = ()


def verify_removal(journal, resources: ResourceObservations, inspector, *, collector=None) -> RemovalResult:
    """No deletes, enumeration, process kills, writes, or retries.

    Exact registry/API storage queries are supplied by NativeProfileAdapter in
    native diagnostics. Operation receipts remain unavailable until a future
    reviewed supervisor collects them from its own handles and trusted paths.
    """
    from .profile_journal import read_record
    identity = dict(operation_id=resources.operation_id, policy_id=resources.policy_id,
                    ownership_token=resources.ownership_token, expected_sid=resources.expected_sid,
                    source=resources.source)

    def result(status, *details):
        return RemovalResult(**identity, status=status, details=details)

    try:
        journal.check_path(journal.path)
        record = read_record(journal.path, resources.operation_id, resources.ownership_token)
        if (record != journal.record or record.policy_id != resources.policy_id
            or record.policy_id != ProfilePolicy().policy_id
            or record.expected_sid != resources.expected_sid
            or record.observed_sid != resources.expected_sid
            or record.state not in ("CLEANING", "CLEANED")):
            return result("VERIFICATION_ERROR", "OWNERSHIP_OR_JOURNAL_CONFLICT")
        if resources.source == "SUPERVISOR_READ_ONLY":
            from .journal_security import validate_journal_preflight
            validate_journal_preflight(journal)
            from .os_receipts import OperationResources
            if type(collector) is not OperationResources:
                return result("VERIFICATION_UNAVAILABLE", "SUPERVISOR_RECEIPT_REQUIRED")
            collector.require_receipt(resources, journal, consume=True)
        if resources.ownership_confirmed is None:
            return result("VERIFICATION_UNAVAILABLE", "PROFILE_OWNERSHIP_NOT_VERIFIED")
        if resources.ownership_confirmed is not True:
            return result("VERIFICATION_ERROR", "OWNERSHIP_OR_JOURNAL_CONFLICT")
        inspection = inspector.inspect_profile()
        if (inspection["profile_name"] != PROFILE_NAME
            or inspection["expected_sid"] != resources.expected_sid
            or type(inspection["mapping_present"]) is not bool
            or type(inspection["folder_present"]) is not bool):
            return result("VERIFICATION_ERROR", "PROFILE_IDENTITY_CONFLICT")
        if inspection["mapping_present"]:
            return result("PROFILE_PRESENT", "EXACT_REGISTRY_MAPPING_PRESENT")
        if inspection["folder_present"]:
            return result("RESIDUAL_RESOURCE_FOUND", "API_STORAGE_PRESENT")
        checks = ("delete_succeeded", "process_stopped", "job_empty", "handles_released",
                  "operation_directories_absent", "tree_absent")
        residual = tuple(key for key in checks if getattr(resources, key) is False)
        if residual:
            return result("RESIDUAL_RESOURCE_FOUND", *residual)
        unknown = tuple(key for key in checks if getattr(resources, key) is None)
        if unknown:
            return result("VERIFICATION_UNAVAILABLE", *unknown)
        return result("PROFILE_ABSENT_IN_CHECKED_LOCATIONS")
    except (PermissionError, FileNotFoundError):
        return result("VERIFICATION_UNAVAILABLE", "INSPECTION_UNAVAILABLE")
    except EvidenceError as error:
        if str(error) == "JOURNAL_SECURITY_NOT_VERIFIED":
            return result("VERIFICATION_UNAVAILABLE", "JOURNAL_SECURITY_NOT_VERIFIED")
        return result("VERIFICATION_ERROR", "INSPECTION_FAILED")
    except WindowsErrorCode as error:
        if error.code == 5:
            return result("VERIFICATION_UNAVAILABLE", "INSPECTION_UNAVAILABLE")
        return result("VERIFICATION_ERROR", "INSPECTION_FAILED")
    except Exception:
        # Never expose paths, registry contents or arbitrary upstream errors.
        return result("VERIFICATION_ERROR", "INSPECTION_FAILED")


def require_cleaned_result(result, record):
    if (type(result) is not RemovalResult
        or result.status != "PROFILE_ABSENT_IN_CHECKED_LOCATIONS"
        or result.operation_id != record.operation_id or result.policy_id != record.policy_id
        or result.ownership_token != record.ownership_token or result.expected_sid != record.expected_sid):
        raise EvidenceError("ROLLBACK_INCOMPLETE")
