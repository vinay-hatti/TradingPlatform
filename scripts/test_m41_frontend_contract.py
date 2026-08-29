from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
ui=root/'ui/workstation'
required=['package.json','vite.config.ts','index.html','src/App.tsx','src/api.ts','src/pages.tsx','src/styles.css']
for item in required: assert (ui/item).is_file(), item
pkg=json.loads((ui/'package.json').read_text())
assert 'react' in pkg['dependencies'] and 'vite' in pkg['dependencies']
api=(ui/'src/api.ts').read_text()
for endpoint in ['/health','/readiness','/overview','/portfolio','/risk','/execution','/positions','/exit-instructions']: assert endpoint in api
app=(ui/'src/App.tsx').read_text()
for page in ['overview','portfolio','risk','execution','positions','exits']: assert page in app
print('Milestone 41 frontend contract assertions passed.')
