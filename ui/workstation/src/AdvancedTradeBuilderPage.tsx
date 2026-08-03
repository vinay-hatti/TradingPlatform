import { useEffect, useMemo, useState } from 'react';
import { executionWorkspaceApi, opportunityApi, tradeBuilderApi } from './api';
import type { OpportunityRecord, TradePlan } from './types';

const n = (v: any, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
const s = (v: any) => String(v ?? '').trim();
const upper = (v: any) => s(v).toUpperCase();

function firstNumber(...values: any[]): number {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return 0;
}

function firstString(...values: any[]): string {
  for (const value of values) {
    const parsed = s(value);
    if (parsed) return parsed;
  }
  return '';
}

function normalizeSide(value: any): string {
  const side = upper(value?.side ?? value?.action);
  if (side.startsWith('BUY')) return 'BUY';
  if (side.startsWith('SELL')) return 'SELL';
  return side;
}

function opportunityStrategy(opportunity: any): string {
  return upper(
    opportunity?.source_payload?.strategy ??
      opportunity?.strategy ??
      opportunity?.metadata?.strategy,
  );
}

function isSingleLegStrategy(strategy: string): boolean {
  return ['LONG_CALL', 'LONG_PUT', 'SHORT_CALL', 'SHORT_PUT'].includes(strategy);
}

function optionRightFor(opportunity: any): string {
  const strategyName = opportunityStrategy(opportunity);
  if (strategyName.includes('PUT')) return 'PUT';
  if (strategyName.includes('CALL')) return 'CALL';
  return upper(opportunity?.direction).includes('PUT') ? 'PUT' : 'CALL';
}

function extractContractLegs(opportunity: any): any[] {
  if (!opportunity) return [];

  const candidates = [
    opportunity.option_contract_legs,
    opportunity.metadata?.option_contract_legs,
    opportunity.source_payload?.option_contract_legs,
    opportunity.legs,
    opportunity.metadata?.legs,
  ];

  for (const value of candidates) {
    if (Array.isArray(value) && value.length > 0) return value;
  }

  const payload = opportunity.source_payload ?? {};
  const optionSymbol = firstString(
    payload.contract_ticker,
    payload.option_symbol,
    payload.option_ticker,
  );

  if (!optionSymbol) return [];

  return [
    {
      side: opportunityStrategy(opportunity).startsWith('SHORT_') ? 'SELL' : 'BUY',
      quantity: Number(payload.contracts ?? 1) || 1,
      option_symbol: optionSymbol,
      option_right: optionRightFor(opportunity),
      strike: payload.strike,
      expiry: payload.expiry,
      bid: payload.bid,
      ask: payload.ask,
      mid: payload.option_entry,
      last: payload.last_price,
      limit_price: payload.option_entry,
    },
  ];
}

export function AdvancedTradeBuilderPage() {
  const [opps, setOpps] = useState<OpportunityRecord[]>([]);
  const [oppId, setOppId] = useState('');
  const [plans, setPlans] = useState<TradePlan[]>([]);
  const [message, setMessage] = useState('');
  const [account, setAccount] = useState('PAPER-PRIMARY');
  const [capital, setCapital] = useState(100000);
  const [risk, setRisk] = useState(1);
  const [strategy, setStrategy] = useState('LONG_CALL');
  const [expiry, setExpiry] = useState('');
  const [longStrike, setLongStrike] = useState(0);
  const [shortStrike, setShortStrike] = useState(0);
  const [longPrice, setLongPrice] = useState(0);
  const [shortPrice, setShortPrice] = useState(0);
  const [longOptionSymbol, setLongOptionSymbol] = useState('');
  const [shortOptionSymbol, setShortOptionSymbol] = useState('');

  const selected = useMemo(
    () => opps.find((x) => x.opportunity_id === oppId),
    [opps, oppId],
  );

  const selectedStrategy = opportunityStrategy(selected);
  const singleLeg = isSingleLegStrategy(strategy);

  const load = async () => {
    const o = await opportunityApi.list();
    const eligible = o.data.filter((x) =>
      ['UNDER_REVIEW', 'APPROVED', 'TRADE_BUILT'].includes(x.workflow_state),
    );
    setOpps(eligible);
    if (!oppId && eligible[0]) setOppId(eligible[0].opportunity_id);
    const p = await tradeBuilderApi.list();
    setPlans(p.data);
  };

  useEffect(() => {
    load().catch((e) => setMessage(e.message));
  }, []);

  useEffect(() => {
    setExpiry('');
    setLongStrike(0);
    setShortStrike(0);
    setLongPrice(0);
    setShortPrice(0);
    setLongOptionSymbol('');
    setShortOptionSymbol('');

    if (!selected) return;

    const inferredStrategy = selectedStrategy || 'LONG_CALL';
    setStrategy(inferredStrategy);

    const legs = extractContractLegs(selected);
    const buy = legs.find((leg) => normalizeSide(leg) === 'BUY');
    const sell = legs.find((leg) => normalizeSide(leg) === 'SELL');
    const primary = buy ?? sell;

    if (!primary) {
      setMessage(
        'Selected opportunity has no executable option contract. Refresh options data or rebuild the opportunity.',
      );
      return;
    }

    setExpiry(firstString(primary.expiry, sell?.expiry));

    if (buy) {
      setLongOptionSymbol(firstString(buy.option_symbol, buy.contract_ticker));
      setLongStrike(firstNumber(buy.strike));
      setLongPrice(firstNumber(buy.ask, buy.mid, buy.limit_price, buy.last, buy.bid));
    }

    if (sell) {
      setShortOptionSymbol(firstString(sell.option_symbol, sell.contract_ticker));
      setShortStrike(firstNumber(sell.strike));
      setShortPrice(firstNumber(sell.bid, sell.mid, sell.limit_price, sell.last, sell.ask));
    }

    if (!buy && sell) {
      setLongOptionSymbol(firstString(sell.option_symbol, sell.contract_ticker));
      setLongStrike(firstNumber(sell.strike));
      setLongPrice(firstNumber(sell.bid, sell.mid, sell.limit_price, sell.last, sell.ask));
    }

    if (isSingleLegStrategy(inferredStrategy)) {
      setShortOptionSymbol('');
      setShortStrike(0);
      setShortPrice(0);
    }

    setMessage('');
  }, [selected, selectedStrategy]);

  const contractReady = Boolean(
    selected &&
      expiry &&
      longOptionSymbol &&
      longStrike > 0 &&
      longPrice > 0 &&
      (singleLeg || (shortOptionSymbol && shortStrike > 0 && shortPrice > 0)),
  );

  const build = async () => {
    if (!selected) return;
    if (!contractReady) {
      setMessage(
        singleLeg
          ? 'Selected opportunity has no executable option contract.'
          : 'Selected spread opportunity has incomplete BUY/SELL contract identities.',
      );
      return;
    }

    setMessage('');
    try {
      const right = optionRightFor(selected);
      const legs = singleLeg
        ? [
            {
              side: strategy.startsWith('SHORT_') ? 'SELL' : 'BUY',
              quantity: 1,
              option_right: right,
              option_symbol: longOptionSymbol,
              strike: longStrike,
              expiry,
              limit_price: longPrice,
            },
          ]
        : [
            {
              side: 'BUY',
              quantity: 1,
              option_right: right,
              option_symbol: longOptionSymbol,
              strike: longStrike,
              expiry,
              limit_price: longPrice,
            },
            {
              side: 'SELL',
              quantity: 1,
              option_right: right,
              option_symbol: shortOptionSymbol,
              strike: shortStrike,
              expiry,
              limit_price: shortPrice,
            },
          ];

      await tradeBuilderApi.build({
        opportunity_id: selected.opportunity_id,
        expected_opportunity_version: selected.version,
        account_id: account,
        strategy,
        capital,
        risk_budget_pct: risk,
        legs,
        notes: 'Created in governed Trade Builder from exact opportunity contract identity',
      });
      setMessage('Trade plan created and validated.');
      await load();
    } catch (e: any) {
      setMessage(e.message);
    }
  };

  const move = async (p: TradePlan, state: string) => {
    try {
      await tradeBuilderApi.transition(
        p.trade_plan_id,
        p.version,
        state,
        `Workstation transition to ${state}`,
      );
      if (state === 'PAPER_READY') {
        const intent = await executionWorkspaceApi.create(p.trade_plan_id, p.account_id);
        setMessage(`Paper execution intent ${intent.data.execution_intent_id} created.`);
        location.hash = '#/execution-workspace';
        return;
      }
      await load();
    } catch (e: any) {
      setMessage(e.message);
    }
  };

  const netDebit = singleLeg ? longPrice * 100 : Math.max(0, (longPrice - shortPrice) * 100);

  return (
    <section>
      <div className="page-title">
        <div>
          <h2>Advanced Trade Builder & Execution</h2>
          <p>
            Construct versioned, defined-risk option plans from canonical opportunities and normalized institutional intelligence.
          </p>
        </div>
      </div>
      {message && <div className="handoff-message">{message}</div>}
      <div className="trade-builder-layout">
        <article className="panel">
          <h3>Construction inputs</h3>
          <div className="scanner-form">
            <label>
              Opportunity
              <select value={oppId} onChange={(e) => setOppId(e.target.value)}>
                <option value="">Select</option>
                {opps.map((o) => (
                  <option key={o.opportunity_id} value={o.opportunity_id}>
                    {o.symbol} · {opportunityStrategy(o) || o.strategy} · v{o.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Paper account
              <input value={account} onChange={(e) => setAccount(e.target.value)} />
            </label>
            <label>
              Capital
              <input type="number" value={capital} onChange={(e) => setCapital(n(e.target.value))} />
            </label>
            <label>
              Risk budget %
              <input type="number" step="0.1" value={risk} onChange={(e) => setRisk(n(e.target.value))} />
            </label>
            <label>
              Strategy
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                <option>LONG_CALL</option>
                <option>LONG_PUT</option>
                <option>SHORT_CALL</option>
                <option>SHORT_PUT</option>
                <option>BULL_CALL_SPREAD</option>
                <option>BEAR_PUT_SPREAD</option>
              </select>
            </label>
            <label>
              Expiry
              <input value={expiry} readOnly />
            </label>
            <label>
              Long/primary contract
              <input value={longOptionSymbol} readOnly />
            </label>
            <label>
              Long/primary strike
              <input type="number" value={longStrike || ''} readOnly />
            </label>
            <label>
              Long/primary price
              <input type="number" step="0.01" value={longPrice || ''} readOnly />
            </label>
            {!singleLeg && (
              <>
                <label>
                  Short contract
                  <input value={shortOptionSymbol} readOnly />
                </label>
                <label>
                  Short strike
                  <input type="number" value={shortStrike || ''} readOnly />
                </label>
                <label>
                  Short price
                  <input type="number" step="0.01" value={shortPrice || ''} readOnly />
                </label>
              </>
            )}
            <button className="primary" onClick={build} disabled={!contractReady}>
              Build governed plan
            </button>
          </div>
        </article>
        <article className="panel">
          <h3>Risk preview</h3>
          <div className="grid metrics">
            <div><span>Net debit</span><b>${netDebit.toFixed(2)}</b></div>
            <div><span>Max loss</span><b>${netDebit.toFixed(2)}</b></div>
            <div><span>Risk budget</span><b>${(capital * risk / 100).toFixed(2)}</b></div>
            <div><span>Defined risk</span><b>{singleLeg || shortStrike !== longStrike ? 'YES' : 'REVIEW'}</b></div>
          </div>
          <p>
            Paper readiness only creates a governed execution intent. It does not enable live trading or bypass existing IBKR paper-routing controls.
          </p>
        </article>
      </div>
      <article className="panel">
        <h3>Trade plans</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Symbol</th><th>Strategy</th><th>State</th><th>Max loss</th><th>R/R</th><th>Version</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.trade_plan_id}>
                  <td>{p.symbol}</td><td>{p.strategy}</td><td>{p.state}</td>
                  <td>${p.max_loss.toFixed(2)}</td><td>{p.reward_risk_ratio ?? '—'}</td><td>{p.version}</td>
                  <td>
                    {p.state === 'VALIDATED' && <button onClick={() => move(p, 'APPROVED')}>Approve</button>}
                    {p.state === 'APPROVED' && <button onClick={() => move(p, 'PAPER_READY')}>Prepare paper intent</button>}
                    {p.state === 'PAPER_READY' && (
                      <button onClick={() => executionWorkspaceApi.create(p.trade_plan_id, p.account_id).then(() => { location.hash = '#/execution-workspace'; }).catch((e: any) => setMessage(e.message))}>
                        Open execution workspace
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
