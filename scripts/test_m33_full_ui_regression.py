from importlib import import_module

MODULES=[
    "trading_ai.ui.api.strategy_studio",
    "trading_ai.ui.api.operations_command_center",
    "trading_ai.ui.api.security_compliance_center",
    "trading_ai.ui.api.executive_reporting",
    "trading_ai.ui.api.ui_resilience",
    "trading_ai.ui.services.strategy_studio_service",
    "trading_ai.ui.services.operations_command_center_service",
    "trading_ai.ui.services.security_compliance_center_service",
    "trading_ai.ui.services.executive_reporting_service",
    "trading_ai.ui.services.ui_resilience_service",
]

def main():
    for module in MODULES:
        import_module(module)
    print("All Milestone 33 UI regression imports passed.")

if __name__=="__main__":
    main()
