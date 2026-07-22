from dataclasses import dataclass
from typing import Iterable
from .contracts import OptionQuoteRecord
@dataclass(frozen=True)
class OptionDeduplicationResult:
    input_record_count:int; unique_record_count:int; duplicate_record_count:int; records:tuple[OptionQuoteRecord,...]
class OptionContractDeduplicator:
    def deduplicate(self,records:Iterable[OptionQuoteRecord])->OptionDeduplicationResult:
        materialized=tuple(records); selected={}
        for r in materialized:
            key=(r.identity.canonical_key,r.quote_date)
            cur=selected.get(key)
            if cur is None or self._rank(r)>self._rank(cur):selected[key]=r
        unique=tuple(sorted(selected.values(),key=lambda x:(x.identity.underlying_symbol,x.quote_date,x.identity.expiration_date,x.identity.strike,x.identity.option_side.value)))
        return OptionDeduplicationResult(len(materialized),len(unique),len(materialized)-len(unique),unique)
    @staticmethod
    def _rank(r):
        return (sum(v is not None for v in (r.bid,r.ask,r.last)),sum(v is not None for v in (r.volume,r.open_interest)),sum(v is not None for v in (r.implied_volatility,r.delta,r.gamma,r.theta,r.vega)),int(bool(r.provider_symbol)))
