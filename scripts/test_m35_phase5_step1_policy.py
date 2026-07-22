from trading_ai.scanner.dashboard import DashboardConfiguration,ScannerDashboardEngine
def main():
 e=ScannerDashboardEngine()
 try:e.create_snapshot(DashboardConfiguration(top_n=15));raise AssertionError('invalid top_n should fail')
 except ValueError:pass
 s=e.create_snapshot()
 try:e.start_scan(s);raise AssertionError('IDLE -> SCANNING should fail')
 except ValueError:pass
 print('Milestone 35 Phase 5 Step 1 policy assertions passed.')
if __name__=='__main__':main()
