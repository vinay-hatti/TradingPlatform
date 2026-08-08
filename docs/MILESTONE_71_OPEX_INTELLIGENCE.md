# Milestone 71 — OPEX Intelligence & Probabilistic Path Forecasting

M71 adds governed OPEX forecasts for SPX, NDX and RUT. It uses persisted dealer strike/expiration profiles, current dealer positioning, underlying trend/realized volatility and governed event intelligence. It publishes 50/68/90% settlement ranges, price magnets, support/resistance, gamma/call/put-wall migration forecasts, daily charm/vanna exposures, dealer hedging pressure, scenario probabilities, confidence decomposition, forecast history and a Cross-OPEX Transition Map.

Forecasts are probabilistic, estimator-derived and never represented as guaranteed settlement prices. Every refresh is timestamped and retained. Expired forecasts can be realized into an outcome table for coverage/magnet calibration.

Both underlying and options finalizers invoke OPEX refresh; options finalization is normally the richer refresh because dealer strike/expiration profiles have just been updated.
