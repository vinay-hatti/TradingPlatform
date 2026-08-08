from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.models import InflectionPublicationModel, InflectionSnapshotModel
from sqlalchemy import select, func

def main():
    with SessionLocal() as s:
        pub=s.execute(select(InflectionPublicationModel).where(InflectionPublicationModel.publication_name=='current_institutional_inflection')).scalars().first()
        count=s.scalar(select(func.count()).select_from(InflectionSnapshotModel)) or 0
        high=s.scalar(select(func.count()).select_from(InflectionSnapshotModel).where(InflectionSnapshotModel.inflection_score>=80)) or 0
        checks={'publication':bool(pub),'snapshots':count>0,'components':False,'timeline_ready':False}
        row=s.execute(select(InflectionSnapshotModel).limit(1)).scalars().first()
        if row:
            checks['components']=all(k in (row.payload_json or {}).get('components',{}) for k in ('trend','structure','dealer','volatility','participation','breadth','liquidity'))
            checks['timeline_ready']=bool((row.payload_json or {}).get('state_hash'))
        for k,v in checks.items(): print(f'{k}: {"PASS" if v else "FAIL"}')
        print(f'Inflection snapshots: {count}; high conviction: {high}')
        if not all(checks.values()): raise SystemExit('Milestone 68 operational acceptance FAILED')
        print('Milestone 68 operational acceptance PASSED')
if __name__=='__main__': main()
