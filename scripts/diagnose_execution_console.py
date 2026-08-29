from trading_ai.ui.services.execution_console_service import ExecutionConsoleService

def main():
    result=ExecutionConsoleService().get()
    print(f"Available: {result.available}")
    print(f"Command mode: {result.command_mode}")
    print(f"Source: {result.source_detail}")
    print(f"Orders: {len(result.orders)}")
    print(f"Fills: {len(result.fills)}")
    print(f"Alerts: {len(result.alerts)}")
    print(f"Fill rate: {result.quality.fill_rate_pct}")
    for notice in result.notices:
        print(f"- {notice}")

if __name__=="__main__": main()
