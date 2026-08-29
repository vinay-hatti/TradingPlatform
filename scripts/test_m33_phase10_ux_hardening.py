from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.ui.services.ui_resilience_service import UiResilienceService

def main():
    with TemporaryDirectory() as d:
        root=Path(d)
        for name in [
            "index.html","app.js","strategy_studio.js",
            "operations_command_center.js","security_compliance_center.js",
            "executive_reporting.js",
        ]:
            (root/name).write_text("test",encoding="utf-8")
        svc=UiResilienceService(root)
        manifest=svc.manifest()
        diagnostics=svc.diagnostics()
        assert manifest["version"]=="33.10.0"
        assert manifest["offline_supported"] is True
        assert diagnostics["status"]=="HEALTHY"
        assert diagnostics["accessibility"]["keyboard_navigation"] is True
        assert diagnostics["resilience"]["service_worker"] is True

    static=Path("src/trading_ai/ui/static")
    assert (static/"ui_hardening.js").exists()
    assert (static/"ui_hardening.css").exists()
    assert (static/"service-worker.js").exists()

    js=(static/"ui_hardening.js").read_text(encoding="utf-8")
    css=(static/"ui_hardening.css").read_text(encoding="utf-8")
    sw=(static/"service-worker.js").read_text(encoding="utf-8")
    assert "fetchWithResilience" in js
    assert "aria-live" in js
    assert "prefers-reduced-motion" in css
    assert "forced-colors" in css
    assert "caches.open" in sw

    print("All Milestone 33 Phase 10 UX Hardening assertions passed.")

if __name__=="__main__":
    main()
