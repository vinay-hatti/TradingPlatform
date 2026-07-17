from __future__ import annotations
from .realtime_market_data_normalizer import parse_timestamp
from .realtime_market_data_policy import RealTimeMarketDataPolicy
from .realtime_market_data_profile import MarketDataQualityCheck, MarketDataQualityProfile

class RealTimeMarketDataQualityEngine:
    def __init__(self, policy=None): self.policy=policy or RealTimeMarketDataPolicy(); self.policy.validate()
    @staticmethod
    def _grade(score):
        return ('A','LOW') if score>=95 else ('B','MODERATE') if score>=85 else ('C','SEVERE') if score>=70 else ('F','CRITICAL')
    def _finalize(self, event_type, symbol, checks, age, stale, out_of_order, future, warnings, metadata):
        req=[c for c in checks if c.required]; failed=[c for c in req if not c.passed]; score=sum(c.score for c in req)/len(req) if req else 100.0
        allowed=(not failed and score>=self.policy.minimum_quality_score) if self.policy.fail_closed else score>=self.policy.minimum_quality_score
        grade,severity=self._grade(score)
        return MarketDataQualityProfile(event_type=event_type,symbol=symbol,valid=True,allowed=allowed,score=round(score,2),grade=grade,severity=severity,recommendation='ACCEPT' if allowed else 'REJECT',event_age_seconds=round(age,6),stale=stale,out_of_order=out_of_order,future_timestamp=future,checks=tuple(checks),warnings=tuple(warnings),rejection_reasons=tuple(c.name.upper() for c in failed),metadata=metadata)
    def evaluate_quote(self,q,previous_exchange_timestamp=None):
        checks=[]; warnings=[]
        def add(name,category,passed,msg,required=True,severity='CRITICAL',metadata=None): checks.append(MarketDataQualityCheck(name,category,bool(passed),required,100.0 if passed else 0.0,'LOW' if passed else severity,msg,metadata or {}))
        add('symbol','identity',bool(q.symbol) or not self.policy.require_symbol,'Symbol is present.')
        add('asset_class','identity',q.asset_class in self.policy.allowed_asset_classes,'Asset class is supported.')
        add('positive_prices','price',not self.policy.require_positive_prices or (q.bid_price>self.policy.minimum_bid_price and q.ask_price>self.policy.minimum_ask_price),'Bid and ask prices meet requirements.')
        crossed=q.bid_price>q.ask_price; locked=q.bid_price==q.ask_price and q.bid_price>0
        add('crossed_quote','price',not crossed or not self.policy.reject_crossed_quotes,'Bid must not exceed ask.')
        add('locked_quote','price',not locked or not self.policy.reject_locked_quotes,'Locked quote policy is satisfied.',severity='SEVERE')
        spread_ok=q.midpoint>0 and q.spread_pct<=self.policy.maximum_spread_pct
        add('spread','liquidity',spread_ok,'Spread is within threshold.',severity='SEVERE',metadata={'spread_pct':q.spread_pct})
        if spread_ok and q.spread_pct>self.policy.warning_spread_pct: warnings.append('WIDE_SPREAD')
        add('quote_size','liquidity',q.bid_size>=self.policy.minimum_quote_size and q.ask_size>=self.policy.minimum_quote_size,'Quote sizes meet requirements.',severity='SEVERE')
        stale=q.event_age_seconds>self.policy.maximum_quote_age_seconds; add('stale_quote','timeliness',not stale or not self.policy.reject_stale_quotes,'Quote age is within policy.')
        if stale and not self.policy.reject_stale_quotes: warnings.append('STALE_QUOTE')
        future=q.event_age_seconds < -self.policy.maximum_future_skew_seconds; add('future_timestamp','timeliness',not future or not self.policy.reject_future_timestamps,'Timestamp is not materially future.')
        prev=parse_timestamp(previous_exchange_timestamp); cur=parse_timestamp(q.exchange_timestamp); out=bool(prev and cur and (prev-cur).total_seconds()>self.policy.maximum_out_of_order_seconds)
        add('out_of_order','sequence',not out or not self.policy.reject_out_of_order_events,'Event is not materially out of order.')
        add('provider_timestamp','timeliness',q.provider_timestamp is not None or not self.policy.require_provider_timestamp,'Provider timestamp policy satisfied.')
        return self._finalize('QUOTE',q.symbol,checks,q.event_age_seconds,stale,out,future,warnings,{'midpoint':q.midpoint,'spread':q.spread,'spread_pct':q.spread_pct})
    def evaluate_trade(self,t,previous_exchange_timestamp=None):
        checks=[]; warnings=[]
        def add(name,category,passed,msg,required=True,severity='CRITICAL',metadata=None): checks.append(MarketDataQualityCheck(name,category,bool(passed),required,100.0 if passed else 0.0,'LOW' if passed else severity,msg,metadata or {}))
        add('symbol','identity',bool(t.symbol) or not self.policy.require_symbol,'Symbol is present.')
        add('asset_class','identity',t.asset_class in self.policy.allowed_asset_classes,'Asset class supported.')
        add('trade_price','price',not self.policy.require_positive_prices or t.price>self.policy.minimum_trade_price,'Trade price meets requirements.')
        add('trade_size','liquidity',t.size>=self.policy.minimum_trade_size,'Trade size meets requirements.',severity='SEVERE')
        stale=t.event_age_seconds>self.policy.maximum_trade_age_seconds; add('stale_trade','timeliness',not stale or not self.policy.reject_stale_trades,'Trade age is within policy.')
        if stale and not self.policy.reject_stale_trades: warnings.append('STALE_TRADE')
        future=t.event_age_seconds < -self.policy.maximum_future_skew_seconds; add('future_timestamp','timeliness',not future or not self.policy.reject_future_timestamps,'Timestamp is not materially future.')
        prev=parse_timestamp(previous_exchange_timestamp); cur=parse_timestamp(t.exchange_timestamp); out=bool(prev and cur and (prev-cur).total_seconds()>self.policy.maximum_out_of_order_seconds)
        add('out_of_order','sequence',not out or not self.policy.reject_out_of_order_events,'Event is not materially out of order.')
        add('provider_timestamp','timeliness',t.provider_timestamp is not None or not self.policy.require_provider_timestamp,'Provider timestamp policy satisfied.')
        return self._finalize('TRADE',t.symbol,checks,t.event_age_seconds,stale,out,future,warnings,{'price':t.price,'size':t.size,'notional':t.notional})
