import { useEffect, useMemo, useState } from 'react';
import { executionWorkspaceApi, opportunityApi, tradeBuilderApi } from './api';
import type { OpportunityRecord, TradePlan } from './types';

const n = (value: unknown, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

type ContractLeg = {
  side?: string;
  action?: string;
  option_symbol?: string;
  optionSymbol?: string;
  option_right?: string;
  option_type?: string;
  right?: string;
  strike?: number | string;
  expiry?: string;
  expiration?: string;
  bid?: number | string;
  ask?: number | string;
  mid?: number | string;
  last?: number | string;
  limit_price?: number | string;
  contract_id?: number | string;
};

type OpportunityWithContracts = OpportunityRecord & {
  option_contract_legs?: ContractLeg[];
  legs?: ContractLeg[];
  metadata?: Record<string, unknown> & {
    option_contract_legs?: ContractLeg[];
  };
};

const legSide = (leg: ContractLeg) =>
  String(leg.side ?? leg.action ?? '').trim().toUpperCase();

const legOptionSymbol = (leg?: ContractLeg) =>
  String(leg?.option_symbol ?? leg?.optionSymbol ?? '').trim();

const legExpiry = (leg?: ContractLeg) =>
  String(leg?.expiry ?? leg?.expiration ?? '').trim();

const legRight = (leg?: ContractLeg, fallback = 'CALL') => {
  const value = String(
    leg?.option_right ?? leg?.option_type ?? leg?.right ?? fallback,
  ).trim().toUpperCase();
  return value === 'PUT' || value === 'P' ? 'PUT' : 'CALL';
};

const buyPrice = (leg?: ContractLeg) =>
  n(leg?.ask ?? leg?.mid ?? leg?.last ?? leg?.limit_price, 0);

const sellPrice = (leg?: ContractLeg) =>
  n(leg?.bid ?? leg?.mid ?? leg?.last ?? leg?.limit_price, 0);

export function AdvancedTradeBuilderPage() {
  const [opps, setOpps] = useState<OpportunityRecord[]>([]);
  const [oppId, setOppId] = useState('');
  const [plans, setPlans] = useState<TradePlan[]>([]);
  const [message, setMessage] = useState('');

  const [account, setAccount] = useState('PAPER-PRIMARY');
  const [capital, setCapital] = useState(100000);
  const [risk, setRisk] = useState(1);
  const [strategy, setStrategy] = useState('BULL_CALL_SPREAD');

  const [expiry, setExpiry] = useState('');
  const [longStrike, setLongStrike] = useState(0);
  const [shortStrike, setShortStrike] = useState(0);
  const [longPrice, setLongPrice] = useState(0);
  const [shortPrice, setShortPrice] = useState(0);
  const [longOptionSymbol, setLongOptionSymbol] = useState('');
  const [shortOptionSymbol, setShortOptionSymbol] = useState('');
  const [longRight, setLongRight] = useState('CALL');
  const [shortRight, setShortRight] = useState('CALL');

  const selected = useMemo(
    () => opps.find((item) => item.opportunity_id === oppId) as OpportunityWithContracts | undefined,
    [opps, oppId],
  );

  const selectedLegs = useMemo<ContractLeg[]>(() => {
    if (!selected) return [];
    const metadataLegs = selected.metadata?.option_contract_legs;
    const legs = selected.option_contract_legs ?? metadataLegs ?? selected.legs ?? [];
    return Array.isArray(legs) ? legs : [];
  }, [selected]);

  const selectedBuyLeg = useMemo(
    () => selectedLegs.find((leg) => legSide(leg) === 'BUY'),
    [selectedLegs],
  );

  const selectedSellLeg = useMemo(
    () => selectedLegs.find((leg) => legSide(leg) === 'SELL'),
    [selectedLegs],
  );

  const load = async () => {
    const opportunities = await opportunityApi.list();
    const available = opportunities.data.filter((item) =>
      ['UNDER_REVIEW', 'APPROVED', 'TRADE_BUILT'].includes(item.workflow_state),
    );
    setOpps(available);
    setOppId((current) => {
      if (current && available.some((item) => item.opportunity_id === current)) {
        return current;
      }
      return available[0]?.opportunity_id ?? '';
    });

    const tradePlans = await tradeBuilderApi.list();
    setPlans(tradePlans.data);
  };

  useEffect(() => {
    load().catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!selected) {
      setExpiry('');
      setLongStrike(0);
      setShortStrike(0);
      setLongPrice(0);
      setShortPrice(0);
      setLongOptionSymbol('');
      setShortOptionSymbol('');
      return;
    }

    setStrategy(String(selected.strategy || 'BULL_CALL_SPREAD').toUpperCase());

    if (!selectedBuyLeg) {
      setExpiry('');
      setLongStrike(0);
      setShortStrike(0);
      setLongPrice(0);
      setShortPrice(0);
      setLongOptionSymbol('');
      setShortOptionSymbol('');
      setMessage(
        'Selected opportunity has no executable BUY option contract. Refresh options data or rebuild the opportunity.',
      );
      return;
    }

    const resolvedExpiry = legExpiry(selectedBuyLeg) || legExpiry(selectedSellLeg);
    setExpiry(resolvedExpiry);
    setLongStrike(n(selectedBuyLeg.strike, 0));
    setLongPrice(buyPrice(selectedBuyLeg));
    setLongOptionSymbol(legOptionSymbol(selectedBuyLeg));
    setLongRight(legRight(selectedBuyLeg));

    if (selectedSellLeg) {
      setShortStrike(n(selectedSellLeg.strike, 0));
      setShortPrice(sellPrice(selectedSellLeg));
      setShortOptionSymbol(legOptionSymbol(selectedSellLeg));
      setShortRight(legRight(selectedSellLeg));
    } else {
      setShortStrike(0);
      setShortPrice(0);
      setShortOptionSymbol('');
      setShortRight(legRight(selectedBuyLeg));
    }

    if (!legOptionSymbol(selectedBuyLeg) || (selectedSellLeg && !legOptionSymbol(selectedSellLeg))) {
      setMessage(
        'Selected opportunity has incomplete option contract identities. Refresh options data or rebuild the opportunity.',
      );
    } else {
      setMessage('');
    }
  }, [selected, selectedBuyLeg, selectedSellLeg]);

  const isLongOnly = strategy.startsWith('LONG_');
  const contractIdentityComplete = Boolean(
    selected &&
      expiry &&
      longStrike > 0 &&
      longPrice > 0 &&
      longOptionSymbol &&
      (isLongOnly || (shortStrike > 0 && shortPrice > 0 && shortOptionSymbol)),
  );

  const build = async () => {
    if (!selected) return;
    if (!contractIdentityComplete) {
      setMessage(
        'Cannot build this plan because the selected opportunity does not contain complete executable option contracts.',
      );
      return;
    }

    setMessage('');
    try {
      const longLeg = {
        side: 'BUY',
        quantity: 1,
        option_right: longRight,
        option_symbol: longOptionSymbol,
        strike: longStrike,
        expiry,
        limit_price: longPrice,
      };

      const legs = isLongOnly
        ? [longLeg]
        : [
            longLeg,
            {
              side: 'SELL',
              quantity: 1,
              option_right: shortRight,
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
        notes: 'Created from exact opportunity option contracts in governed trade builder',
      });
      setMessage('Trade plan created and validated.');
      await load();
    } catch (error: any) {
      setMessage(error.message);
    }
  };

  const move = async (plan: TradePlan, state: string) => {
    try {
      await tradeBuilderApi.transition(
        plan.trade_plan_id,
        plan.version,
        state,
        `Workstation transition to ${state}`,
      );
      if (state === 'PAPER_READY') {
        const intent = await executionWorkspaceApi.create(plan.trade_plan_id, plan.account_id);
        setMessage(`Paper execution intent ${intent.data.execution_intent_id} created.`);
        location.hash = '#/execution-workspace';
        return;
      }
      await load();
    } catch (error: any) {
      setMessage(error.message);
    }
  };

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
              <select value={oppId} onChange={(event) => setOppId(event.target.value)}>
                <option value="">Select</option>
                {opps.map((opportunity) => (
                  <option key={opportunity.opportunity_id} value={opportunity.opportunity_id}>
                    {opportunity.symbol} · {opportunity.strategy} · v{opportunity.version}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Paper account
              <input value={account} onChange={(event) => setAccount(event.target.value)} />
            </label>
            <label>
              Capital
              <input type="number" value={capital} onChange={(event) => setCapital(n(event.target.value))} />
            </label>
            <label>
              Risk budget %
              <input type="number" step="0.1" value={risk} onChange={(event) => setRisk(n(event.target.value))} />
            </label>

            <label>
              Strategy
              <select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
                <option>BULL_CALL_SPREAD</option>
                <option>BEAR_PUT_SPREAD</option>
                <option>LONG_CALL</option>
                <option>LONG_PUT</option>
              </select>
            </label>
            <label>
              Expiry
              <input value={expiry} onChange={(event) => setExpiry(event.target.value)} />
            </label>
            <label>
              Long strike
              <input type="number" value={longStrike || ''} onChange={(event) => setLongStrike(n(event.target.value))} />
            </label>
            <label>
              Long price
              <input type="number" step="0.01" value={longPrice || ''} onChange={(event) => setLongPrice(n(event.target.value))} />
            </label>
            <label>
              Short strike
              <input
                type="number"
                value={shortStrike || ''}
                disabled={isLongOnly}
                onChange={(event) => setShortStrike(n(event.target.value))}
              />
            </label>
            <label>
              Short price
              <input
                type="number"
                step="0.01"
                value={shortPrice || ''}
                disabled={isLongOnly}
                onChange={(event) => setShortPrice(n(event.target.value))}
              />
            </label>

            <button className="primary" onClick={build} disabled={!contractIdentityComplete}>
              Build governed plan
            </button>
          </div>

          {selected && !contractIdentityComplete && (
            <p className="validation-message">
              This opportunity does not contain complete executable option-contract identities. Rebuild it from the current Polygon option chain.
            </p>
          )}
        </article>

        <article className="panel">
          <h3>Risk preview</h3>
          <div className="grid metrics">
            <div>
              <span>Net debit</span>
              <b>${Math.max(0, (longPrice - shortPrice) * 100).toFixed(2)}</b>
            </div>
            <div>
              <span>Max loss</span>
              <b>${Math.max(0, (longPrice - shortPrice) * 100).toFixed(2)}</b>
            </div>
            <div>
              <span>Risk budget</span>
              <b>${((capital * risk) / 100).toFixed(2)}</b>
            </div>
            <div>
              <span>Defined risk</span>
              <b>{isLongOnly || shortStrike !== longStrike ? 'YES' : 'REVIEW'}</b>
            </div>
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
              <tr>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>State</th>
                <th>Max loss</th>
                <th>R/R</th>
                <th>Version</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.trade_plan_id}>
                  <td>{plan.symbol}</td>
                  <td>{plan.strategy}</td>
                  <td>{plan.state}</td>
                  <td>${plan.max_loss.toFixed(2)}</td>
                  <td>{plan.reward_risk_ratio ?? '—'}</td>
                  <td>{plan.version}</td>
                  <td>
                    {plan.state === 'VALIDATED' && (
                      <button onClick={() => move(plan, 'APPROVED')}>Approve</button>
                    )}
                    {plan.state === 'APPROVED' && (
                      <button onClick={() => move(plan, 'PAPER_READY')}>Prepare paper intent</button>
                    )}
                    {plan.state === 'PAPER_READY' && (
                      <button
                        onClick={() =>
                          executionWorkspaceApi
                            .create(plan.trade_plan_id, plan.account_id)
                            .then(() => {
                              location.hash = '#/execution-workspace';
                            })
                            .catch((error: any) => setMessage(error.message))
                        }
                      >
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
