from trading_ai.app.bootstrap import container

chain = container.options_engine._load_chain("AAPL")

print(type(chain[0]))

o = chain[0]

for attr in sorted(dir(o)):
    if attr.startswith("_"):
        continue

    try:
        print(f"{attr:25} {getattr(o, attr)}")
    except Exception:
        pass
