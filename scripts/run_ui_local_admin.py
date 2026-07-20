from __future__ import annotations
import os
import uvicorn

os.environ.setdefault("UI_LOCAL_ADMIN_MODE", "true")
os.environ.setdefault("UI_BIND_HOST", "127.0.0.1")
os.environ.setdefault("UI_LOCAL_ADMIN_USER_ID", "local-workstation-admin")
os.environ.setdefault("UI_LOCAL_ADMIN_DISPLAY_NAME", "Local Workstation Administrator")

from trading_ai.ui.security.local_admin import require_localhost_bind
require_localhost_bind()

if __name__ == "__main__":
    uvicorn.run("trading_ai.ui.app:app", host=os.environ["UI_BIND_HOST"], port=8080, reload=False)
