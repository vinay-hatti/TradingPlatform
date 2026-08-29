from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from trading_ai.ui.security.local_admin import LOCAL_ADMIN_PERMISSIONS,current_local_admin,require_localhost_bind
from trading_ai.ui.services.local_admin_audit_service import LocalAdminAuditService

def main():
    with patch("trading_ai.ui.security.local_admin.settings.ui_local_admin_mode",True), \
         patch("trading_ai.ui.security.local_admin.settings.ui_bind_host","127.0.0.1"), \
         patch("trading_ai.ui.security.local_admin.settings.ui_local_admin_user_id","local-admin"), \
         patch("trading_ai.ui.security.local_admin.settings.ui_local_admin_display_name","Local Admin"):
        require_localhost_bind();actor=current_local_admin()
        assert actor.local_admin_mode and actor.user_id=="local-admin"
        assert actor.has_permission("security.entitlement.apply")
        assert actor.has_permission("operations.runtime.execute")
        assert set(LOCAL_ADMIN_PERMISSIONS).issubset(set(actor.permissions))
        with TemporaryDirectory() as d:
            path=Path(d)/"events.jsonl"
            event=LocalAdminAuditService(path).record(actor=actor,action="APPLY_ENTITLEMENT",
                resource_type="ENTITLEMENT_CHANGE",resource_id="entitlement-test",
                confirmation_token="CONFIRM-SECURITY-TEST")
            assert event["approval_mode"]=="LOCAL_ADMIN_OVERRIDE" and path.exists()
    with patch("trading_ai.ui.security.local_admin.settings.ui_local_admin_mode",True), \
         patch("trading_ai.ui.security.local_admin.settings.ui_bind_host","0.0.0.0"):
        try:require_localhost_bind();raise AssertionError("Unsafe bind accepted")
        except RuntimeError as exc:assert "localhost-only" in str(exc)
    static=Path("src/trading_ai/ui/static")
    assert (static/"local_admin_mode.js").exists()
    assert (static/"local_admin_mode.css").exists()
    print("All Milestone 33 Phase 10.1 Local Admin Mode assertions passed.")

if __name__=="__main__":main()
