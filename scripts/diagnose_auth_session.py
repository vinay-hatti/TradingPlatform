from trading_ai.ui.services.auth_session_service import AuthSessionService


def main():
    result = AuthSessionService().get()
    print(f"Available: {result.available}")
    print(f"Source: {result.source_detail}")
    print(f"Status: {result.governance.session_status}")
    print(f"Authenticated: {result.governance.authenticated}")
    print(f"Active: {result.governance.active}")
    print(f"Privileged: {result.governance.privileged}")
    print(f"Roles: {result.governance.active_role_count}")
    print(
        "Denied permissions: "
        f"{result.governance.denied_permission_count}"
    )
    print(
        "Enforcement: "
        f"{result.governance.enforcement_mode}"
    )
    if result.identity:
        print(
            f"Identity: {result.identity.display_name} "
            f"({result.identity.user_id})"
        )
    for notice in result.notices:
        print(f"- {notice}")


if __name__ == "__main__":
    main()
