from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.dashboard import RankingRecord,ScannerDashboardEngine
from trading_ai.scanner.dashboard.reporting import write_dashboard_html
def main():
 e=ScannerDashboardEngine();s=e.create_snapshot();s=e.initialize_universe(s,universe_name='TEST',universe_size=1);s=e.start_scan(s);s=e.update_rankings(s,[RankingRecord('AAPL',1,.95,.78,.04,'TREND_UP')])
 with TemporaryDirectory() as d:
  p=write_dashboard_html(Path(d)/'dashboard.html',s);h=p.read_text();assert 'Institutional Scanner Dashboard' in h and 'AAPL' in h and 'TREND_UP' in h
 print('Milestone 35 Phase 5 Step 1 reporting assertions passed.')
if __name__=='__main__':main()
