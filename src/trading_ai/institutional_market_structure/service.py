from __future__ import annotations
import json
from datetime import date,timedelta
from pathlib import Path
from sqlalchemy import delete,select
from trading_ai.database.repositories.option_chain import OptionChainRepository
from trading_ai.database.session import create_session
from trading_ai.market.models import PriceHistory
from .contracts import DealerPositioningPolicy,InstitutionalMarketStructureSnapshot
from .engine import InstitutionalMarketStructureEngine
from .reporting import write_html_report
from .serialization import write_snapshot

class InstitutionalMarketStructureService:
    def __init__(self,policy:DealerPositioningPolicy|None=None): self.policy=policy or DealerPositioningPolicy(); self.engine=InstitutionalMarketStructureEngine(self.policy)
    def run(self,symbol:str,as_of:date,output_dir:Path=Path('reports/m44'),persist:bool=True,write_reports:bool=True)->InstitutionalMarketStructureSnapshot:
        symbol=symbol.upper()
        with create_session() as session:
            repo=OptionChainRepository(session); rows=repo.get_latest_snapshot(symbol,as_of)
            if not rows: raise ValueError(f'No persisted option snapshot found for {symbol} on or before {as_of}')
            qdate=max(r['quote_date'] for r in rows)
            age=(as_of-qdate).days
            if age>self.policy.maximum_snapshot_age_days: raise ValueError(f'Latest option snapshot for {symbol} is {age} days old ({qdate}); maximum allowed is {self.policy.maximum_snapshot_age_days}')
            price=session.scalar(select(PriceHistory).where(PriceHistory.symbol==symbol,PriceHistory.date<=qdate).order_by(PriceHistory.date.desc()).limit(1))
            if price is None: raise ValueError(f'No persisted underlying price found for {symbol} on or before option snapshot {qdate}')
            hist=list(session.scalars(select(PriceHistory).where(PriceHistory.symbol==symbol,PriceHistory.date>=qdate-timedelta(days=90),PriceHistory.date<=qdate).order_by(PriceHistory.date)))
            realized=None; closes=[float(x.close) for x in hist if x.close and x.close>0]
            if len(closes)>=21:
                from math import log,sqrt
                from statistics import pstdev
                rr=[log(closes[i]/closes[i-1]) for i in range(1,len(closes))]; realized=pstdev(rr[-20:])*sqrt(252)
            previous=self._load_previous(session,symbol,as_of)
            snapshot=self.engine.analyze(symbol,as_of,float(price.close),rows,realized,repo.resolved_table_name or 'option_contract_history',previous)
            if persist: self._persist(session,snapshot)
        if write_reports:
            target=output_dir/snapshot.option_snapshot_date
            write_snapshot(snapshot,target)
            write_html_report(snapshot,target/f'{symbol.lower()}_{snapshot.as_of_date}.html')
        return snapshot

    @staticmethod
    def _load_previous(session,symbol,as_of):
        from .database_models import DealerPositionSnapshotModel
        row=session.scalar(select(DealerPositionSnapshotModel).where(DealerPositionSnapshotModel.symbol==symbol,DealerPositionSnapshotModel.as_of_date<as_of).order_by(DealerPositionSnapshotModel.as_of_date.desc()).limit(1))
        if row is None:return None
        from .serialization import snapshot_from_dict
        try:return snapshot_from_dict(json.loads(row.payload_json))
        except Exception:return None

    @staticmethod
    def _persist(session,s):
        from .database_models import DealerExpirationProfileModel,DealerPositionSnapshotModel,DealerStrikeProfileModel,IVSurfaceSnapshotModel
        ad=date.fromisoformat(s.as_of_date)
        session.merge(DealerPositionSnapshotModel.from_snapshot(s))
        for model in (DealerStrikeProfileModel,DealerExpirationProfileModel,IVSurfaceSnapshotModel): session.execute(delete(model).where(model.symbol==s.symbol,model.as_of_date==ad))
        session.add_all([DealerStrikeProfileModel(symbol=s.symbol,as_of_date=ad,expiry=date.fromisoformat(x.expiry),strike=x.strike,dte=x.dte,call_open_interest=x.call_open_interest,put_open_interest=x.put_open_interest,call_volume=x.call_volume,put_volume=x.put_volume,call_gamma_exposure=x.call_gamma_exposure,put_gamma_exposure=x.put_gamma_exposure,net_gamma_exposure=x.net_gamma_exposure,call_delta_exposure=x.call_delta_exposure,put_delta_exposure=x.put_delta_exposure,net_delta_exposure=x.net_delta_exposure,vanna_exposure=x.vanna_exposure,charm_exposure=x.charm_exposure,call_spread_pct=x.call_spread_pct,put_spread_pct=x.put_spread_pct,liquidity_score=x.liquidity_score,dealer_pressure_score=x.dealer_pressure_score,pin_score=x.pin_score,market_structure_eligible=x.market_structure_eligible,trade_eligible=x.trade_eligible) for x in s.strike_exposures])
        session.add_all([DealerExpirationProfileModel(symbol=s.symbol,as_of_date=ad,expiry=date.fromisoformat(x.expiry),dte=x.dte,call_open_interest=x.call_open_interest,put_open_interest=x.put_open_interest,net_gamma_exposure=x.net_gamma_exposure,net_delta_exposure=x.net_delta_exposure,net_vanna_exposure=x.net_vanna_exposure,net_charm_exposure=x.net_charm_exposure,atm_implied_volatility=x.atm_implied_volatility,expected_move=x.expected_move,liquidity_score=x.liquidity_score) for x in s.expiration_exposures])
        session.add_all([IVSurfaceSnapshotModel(symbol=s.symbol,as_of_date=ad,expiry=date.fromisoformat(x.expiry),strike=x.strike,option_type=x.option_type,dte=x.dte,moneyness=x.moneyness,delta=x.delta,implied_volatility=x.implied_volatility,bid=x.bid,ask=x.ask,mid=x.mid,spread_pct=x.spread_pct) for x in s.iv_surface]); session.commit()
