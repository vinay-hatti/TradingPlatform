# Milestone 53 — Index Trend Intelligence Correction

Adds SPX, NDX, and RUT to Base Trend Intelligence and Institutional Trend Intelligence. Transition Intelligence then receives the new Base snapshots. Institutional analysis uses governed listed ETF volume proxies because cash indexes have no native traded volume:

- SPX → SPY
- NDX → QQQ
- RUT → IWM

Forecast Intelligence already supported the three indexes through `price_history`; it is rebuilt for consistency.
