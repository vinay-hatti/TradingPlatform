import { Fragment, useEffect, useMemo, useState } from 'react';
import { executionWorkspaceApi, institutionalOptionsApi, opportunityApi, tradeBuilderApi } from './api';
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

function managementSummary(plan: TradePlan): any {
  return plan.execution_intent?.dynamic_management || {};
}
function portfolioDecision(plan: TradePlan): any {
  return (plan.execution_intent as any)?.portfolio_decision || (plan.execution_intent as any)?.decision_snapshot?.portfolio_decision || {};
}

type ValidationReviewRow = { check: string; actual: string; allowed: string };

function validationReviewRows(plan: TradePlan): ValidationReviewRow[] {
  const failed = Object.entries(plan.validation || {}).filter(([key, value]) => key !== 'valid' && value === false);
  const legs = Array.isArray(plan.legs) ? plan.legs : [];
  const expiries = new Set(legs.map((x:any)=>String(x?.expiry||'')).filter(Boolean));
  const identified = legs.filter((x:any)=>String(x?.option_symbol||'').trim()).length;
  return failed.map(([check]) => {
    switch (check) {
      case 'risk_within_budget':
        return {check, actual: `Max loss $${Number(plan.max_loss||0).toFixed(2)}`, allowed: `≤ $${Number(plan.risk_budget_amount||0).toFixed(2)} (${Number(plan.risk_budget_pct||0).toFixed(2)}% of $${Number(plan.capital||0).toFixed(2)})`};
      case 'option_contract_identity_present':
      case 'm62_exact_polygon_contracts':
        return {check, actual: `${identified} of ${legs.length} legs have exact option identity`, allowed: 'Every option leg must have an exact option_symbol'};
      case 'has_legs':
        return {check, actual: `${legs.length} legs`, allowed: 'At least 1 leg'};
      case 'max_four_legs':
        return {check, actual: `${legs.length} legs`, allowed: 'Maximum 4 legs'};
      case 'positive_quantities': {
        const quantities = legs.map((x:any)=>Number(x?.quantity||0));
        return {check, actual: quantities.length ? quantities.join(', ') : 'No quantities', allowed: 'Every quantity must be > 0'};
      }
      case 'single_expiry':
        return {check, actual: expiries.size ? Array.from(expiries).join(', ') : 'No expiry', allowed: 'Exactly 1 unique expiry'};
      case 'defined_risk':
        return {check, actual: `Max loss ${Number.isFinite(Number(plan.max_loss)) ? `$${Number(plan.max_loss).toFixed(2)}` : 'not finite'}`, allowed: 'Defined finite maximum loss required'};
      case 'm62_selected_strategy':
        return {check, actual: 'Selected strategy lineage missing', allowed: 'Selected Institutional Options strategy required'};
      case 'm62_thesis_lineage':
        return {check, actual: 'Underlying thesis lineage missing', allowed: 'Stock Intelligence thesis/run lineage required'};
      case 'm62_dynamic_management':
        return {check, actual: 'Dynamic management evidence missing', allowed: 'Underlying stop and targets required'};
      case 'm62_override_governance':
        return {check, actual: 'Override governance failed', allowed: 'All overrides must satisfy handoff policy'};
      default:
        return {check, actual: 'Failed', allowed: 'Validation check must pass'};
    }
  });
}

function validationLabel(value: string): string {
  return value.replaceAll('_',' ').replace(/\b\w/g,(c)=>c.toUpperCase());
}

export function AdvancedTradeBuilderPage() {
  const [opps, setOpps] = useState<OpportunityRecord[]>([]);
  const [oppId, setOppId] = useState('');
  const [plans, setPlans] = useState<TradePlan[]>([]);
  const [message, setMessage] = useState('');
  const [reviewPlanId, setReviewPlanId] = useState('');
  const [revalidatingPlanId, setRevalidatingPlanId] = useState('');
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
    const [o, p, config] = await Promise.all([
      opportunityApi.list(),
      tradeBuilderApi.list(),
      institutionalOptionsApi.tradeBuilderConfig(),
    ]);
    const eligible = o.data.filter((x) =>
      ['UNDER_REVIEW', 'APPROVED', 'TRADE_BUILT'].includes(x.workflow_state),
    );
    setOpps(eligible);
    if (!oppId && eligible[0]) setOppId(eligible[0].opportunity_id);
    setPlans(p.data);
    setCapital(n((config.data as any)?.capital, 100000));
    setRisk(n((config.data as any)?.risk_budget_pct, 1));
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

  const revalidatePlan = async (plan: TradePlan) => {
    setRevalidatingPlanId(plan.trade_plan_id);
    setMessage('');
    try {
      const response = await tradeBuilderApi.revalidate(plan.trade_plan_id);
      const refreshed = response.data;
      await load();
      if (refreshed.state === 'VALIDATED') {
        setReviewPlanId('');
        setMessage(`${refreshed.symbol} revalidation passed. Trade plan advanced to VALIDATED; approval remains a separate governed action.`);
      } else {
        setReviewPlanId(refreshed.trade_plan_id);
        setMessage(`${refreshed.symbol} revalidation completed. Trade plan remains DRAFT; review the refreshed failed checks below.`);
      }
    } catch (e:any) {
      setMessage(e.message);
    } finally {
      setRevalidatingPlanId('');
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
      {plans.some(p=>Object.keys(managementSummary(p)).length>0)&&<article className="panel"><h3>Institutional management handoff</h3><p>Plans created from Institutional Options carry their dynamic stop, targets, trailing, theta, volatility, and assignment rules into the Execution Workspace. They are activated after a confirmed fill.</p><div className="grid metrics">{(()=>{const p=plans.find(x=>x.trade_plan_id===sessionStorage.getItem('m62_trade_plan_id'))||plans.find(x=>Object.keys(managementSummary(x)).length>0);const m=p?managementSummary(p):{};return <><div><span>Structural stop</span><b>{m.underlying_stop==null?'—':`$${Number(m.underlying_stop).toFixed(2)}`}</b></div><div><span>Targets</span><b>{(m.underlying_targets||[]).map((x:number)=>`$${Number(x).toFixed(2)}`).join(' · ')||'—'}</b></div><div><span>Trailing policy</span><b>{String(m.trailing_policy||'—').replaceAll('_',' ')}</b></div><div><span>Activation</span><b>After confirmed fill</b></div></>})()}</div></article>}
      <article className="panel">
        <h3>Trade plans</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Symbol</th><th>Strategy</th><th>State</th><th>Max loss</th><th>Portfolio decision</th><th>Dynamic management</th><th>Version</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <Fragment key={p.trade_plan_id}>
                  <tr>
                    <td>{p.symbol}</td><td>{p.strategy}</td><td>{p.state}</td>
                    <td>${p.max_loss.toFixed(2)}</td><td>{(()=>{const d=portfolioDecision(p);return Object.keys(d).length?<span title={(d.explainability?.positive_reasons||[]).join(' · ')}>Fit {Number(d.scores?.portfolio_fit_score||0).toFixed(0)} · Qty {d.capital_allocation?.recommended_quantity??'—'} · {String(d.decision||'REVIEW').replaceAll('_',' ')}</span>:<span className="warning-text">Not assessed</span>})()}</td><td>{(()=>{const m=managementSummary(p);return Object.keys(m).length?<span title={`Stop ${m.underlying_stop ?? '—'} · Targets ${(m.underlying_targets||[]).join(', ')}`}>Attached · {m.trailing_policy?.replaceAll('_',' ')||'governed exits'}</span>:<span className="warning-text">Not attached</span>})()}</td><td>{p.version}</td>
                    <td className="trade-plan-actions">
                      {p.state === 'DRAFT' && <button onClick={() => setReviewPlanId(reviewPlanId===p.trade_plan_id?'':p.trade_plan_id)} title="Review failed validation checks and governed limits">{reviewPlanId===p.trade_plan_id?'Hide validation':'Review validation'}</button>}
                      {p.state === 'VALIDATED' && <button onClick={() => move(p, 'APPROVED')}>Approve</button>}
                      {p.state === 'APPROVED' && <button onClick={() => move(p, 'PAPER_READY')}>Prepare paper intent</button>}
                      {p.state === 'PAPER_READY' && (
                        <button onClick={() => executionWorkspaceApi.create(p.trade_plan_id, p.account_id).then(() => { location.hash = '#/execution-workspace'; }).catch((e: any) => setMessage(e.message))}>
                          Open execution workspace
                        </button>
                      )}
                      {p.state === 'CANCELLED' && <span>Cancelled</span>}
                      {!['DRAFT','VALIDATED','APPROVED','PAPER_READY','CANCELLED'].includes(p.state) && <span>No governed action for {p.state}</span>}
                    </td>
                  </tr>
                  {reviewPlanId === p.trade_plan_id && p.state === 'DRAFT' && (
                    <tr className="trade-validation-review-row">
                      <td colSpan={8}>
                        <div className="trade-validation-review">
                          <div className="trade-validation-review-title">
                            <div><h4>Validation review · {p.symbol} · {p.strategy}</h4><p>{p.trade_plan_id}</p></div>
                            <div className="trade-validation-review-actions">
                              <button onClick={()=>revalidatePlan(p)} disabled={revalidatingPlanId===p.trade_plan_id}>{revalidatingPlanId===p.trade_plan_id?'Revalidating…':'Revalidate'}</button>
                              <button onClick={()=>setReviewPlanId('')} disabled={revalidatingPlanId===p.trade_plan_id}>Close</button>
                            </div>
                          </div>
                          <div className="grid metrics">
                            <div><span>Capital</span><b>${Number(p.capital||0).toFixed(2)}</b></div>
                            <div><span>Risk budget</span><b>{Number(p.risk_budget_pct||0).toFixed(2)}%</b></div>
                            <div><span>Maximum allowed</span><b>${Number(p.risk_budget_amount||0).toFixed(2)}</b></div>
                            <div><span>Trade max loss</span><b>${Number(p.max_loss||0).toFixed(2)}</b></div>
                          </div>
                          {validationReviewRows(p).length ? (
                            <div className="table-wrap"><table><thead><tr><th>Failed validation</th><th>Actual</th><th>Allowed / required</th></tr></thead><tbody>
                              {validationReviewRows(p).map((row)=><tr key={row.check}><td><b>{validationLabel(row.check)}</b></td><td>{row.actual}</td><td>{row.allowed}</td></tr>)}
                            </tbody></table></div>
                          ) : <p>No individual failed checks are persisted for this DRAFT plan. The aggregate validation state is {String(p.validation?.valid)}.</p>}
                          <p className="warning-text">Revalidate reloads current governed Trade Builder risk settings and reruns validation. M62 plans also refresh the current selected recommendation, exact contracts, economics, lineage, and management evidence. A clean pass may advance DRAFT → VALIDATED only; approval remains a separate governed action.</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}
