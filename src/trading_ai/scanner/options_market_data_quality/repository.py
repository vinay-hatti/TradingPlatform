from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from .contracts import OptionQuoteRecord
from .normalization import OptionQuoteNormalizer
@dataclass(frozen=True)
class OptionChainQuery:
    underlying_symbols: tuple[str,...]
    quote_date_start: date
    quote_date_end: date
    minimum_expiration_date: date|None=None
    maximum_expiration_date: date|None=None
class HistoricalOptionChainRepository:
    def __init__(self,database:Session|Engine,normalizer:OptionQuoteNormalizer|None=None):
        self.database=database; self.normalizer=normalizer or OptionQuoteNormalizer()
    def fetch_records(self,query:OptionChainQuery)->tuple[OptionQuoteRecord,...]:
        symbols=tuple(sorted({s.strip().upper() for s in query.underlying_symbols if s and s.strip()}))
        if not symbols:return ()
        clauses=['UPPER(underlying_symbol) IN :symbols','quote_date >= :quote_date_start','quote_date <= :quote_date_end']
        params={'symbols':symbols,'quote_date_start':query.quote_date_start,'quote_date_end':query.quote_date_end}
        if query.minimum_expiration_date is not None:
            clauses.append('expiry >= :minimum_expiration_date'); params['minimum_expiration_date']=query.minimum_expiration_date
        if query.maximum_expiration_date is not None:
            clauses.append('expiry <= :maximum_expiration_date'); params['maximum_expiration_date']=query.maximum_expiration_date
        sql='SELECT underlying_symbol,expiry,quote_date,strike,option_type,bid,ask,last,volume,open_interest,implied_volatility,delta,gamma,theta,vega FROM option_contract_history WHERE '+ ' AND '.join(clauses) +' ORDER BY underlying_symbol,quote_date,expiry,strike,option_type'
        stmt=text(sql).bindparams(bindparam('symbols',expanding=True))
        rows=self._execute(stmt,params)
        return tuple(self._normalize_row(r) for r in rows)
    def fetch_latest_quote_date(self,symbols:Sequence[str])->date|None:
        normalized=tuple(sorted({s.strip().upper() for s in symbols if s}))
        if not normalized:return None
        stmt=text('SELECT MAX(quote_date) FROM option_contract_history WHERE UPPER(underlying_symbol) IN :symbols').bindparams(bindparam('symbols',expanding=True))
        params={'symbols':normalized}
        if isinstance(self.database,Engine):
            with self.database.connect() as c:return c.execute(stmt,params).scalar_one_or_none()
        return self.database.execute(stmt,params).scalar_one_or_none()
    def count_records(self,symbols:Sequence[str],quote_date_start:date,quote_date_end:date)->int:
        normalized=tuple(sorted({s.strip().upper() for s in symbols if s}))
        if not normalized:return 0
        stmt=text('SELECT COUNT(*) FROM option_contract_history WHERE UPPER(underlying_symbol) IN :symbols AND quote_date>=:quote_date_start AND quote_date<=:quote_date_end').bindparams(bindparam('symbols',expanding=True))
        p={'symbols':normalized,'quote_date_start':quote_date_start,'quote_date_end':quote_date_end}
        if isinstance(self.database,Engine):
            with self.database.connect() as c:return int(c.execute(stmt,p).scalar_one())
        return int(self.database.execute(stmt,p).scalar_one())
    def _execute(self,stmt,params):
        if isinstance(self.database,Engine):
            with self.database.connect() as c:return tuple(c.execute(stmt,params).mappings())
        return tuple(self.database.execute(stmt,params).mappings())
    def _normalize_row(self,row):
        return self.normalizer.normalize({'underlying_symbol':row['underlying_symbol'],'expiration_date':row['expiry'],'quote_date':row['quote_date'],'strike':row['strike'],'option_side':row['option_type'],'bid':row['bid'],'ask':row['ask'],'last':row['last'],'volume':row['volume'],'open_interest':row['open_interest'],'implied_volatility':row['implied_volatility'],'delta':row['delta'],'gamma':row['gamma'],'theta':row['theta'],'vega':row['vega']})
def group_records_by_symbol(records:Iterable[OptionQuoteRecord])->dict[str,tuple[OptionQuoteRecord,...]]:
    grouped=defaultdict(list)
    for r in records:grouped[r.identity.underlying_symbol].append(r)
    return {s:tuple(sorted(v,key=lambda x:(x.quote_date,x.identity.expiration_date,x.identity.strike,x.identity.option_side.value))) for s,v in grouped.items()}
