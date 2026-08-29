from __future__ import annotations


def result_exit_code(command: str, result: object) -> int:
    """Map governed operator results to stable process exit codes.

    Audit, status, and materialization are observational operations. Their
    expected fail-closed readiness state is not an operational error. Only an
    explicitly requested training attempt reports insufficient evidence with
    exit code 3.
    """
    if (
        command == "train"
        and isinstance(result, dict)
        and result.get("status") == "INSUFFICIENT_EVIDENCE"
    ):
        return 3
    return 0
