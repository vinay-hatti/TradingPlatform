# Milestone 71.3 — Institutional OPEX Decision Intelligence

M71.3 is additive to M71.2. It preserves the calibrated statistical settlement ranges while improving the decision layer:

- signed, weighted scenario-evidence attribution;
- concentric magnet-zone probability/attraction bands;
- volatility- and strike-spacing-aware staged path objectives;
- non-zero conditional actionable decision zones;
- ranked historical OPEX analogs with similarity and outcomes;
- expected trading-day path into OPEX with event/charm/vanna/futures drivers;
- cross-OPEX scenario transition probability matrices.

The transition matrix is a model-conditioned prior until enough realized OPEX calibration samples exist to estimate empirical transition probabilities.

No new database migration is required because all M71.3 outputs live inside the existing OPEX forecast JSON payload.
