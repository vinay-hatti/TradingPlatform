from fastapi.testclient import TestClient
from trading_ai.ui.app import create_app
c=TestClient(create_app())
assert c.get('/api/v1/health').json()['status']=='healthy'
assert c.get('/api/v1/readiness').json()['ready'] is True
assert c.get('/api/v1/dashboard').status_code==200
assert 'Trading AI Workstation' in c.get('/').text
assert c.get('/static/styles.css').status_code==200
print('All Milestone 31 Phase 1 UI foundation assertions passed.')
