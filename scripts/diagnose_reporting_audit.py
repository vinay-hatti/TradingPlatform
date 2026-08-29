from trading_ai.ui.services.reporting_audit_service import ReportingAuditService


def main():
    result = ReportingAuditService().get()
    print(f"Available: {result.available}")
    print(f"Source: {result.source_detail}")
    print(f"Reports: {result.summary.report_count}")
    print(f"Audit events: {result.summary.audit_event_count}")
    print(f"Verified reports: {result.summary.verified_report_count}")
    print(f"Failed integrity: {result.summary.failed_integrity_count}")
    print(f"Stale reports: {result.summary.stale_report_count}")
    print("Governance:")
    for item in result.governance:
        print(
            f"  - {item.control}: {item.status} "
            f"evidence={item.evidence_count}"
        )
    print("Notices:")
    for notice in result.notices:
        print(f"  - {notice}")


if __name__ == "__main__":
    main()
