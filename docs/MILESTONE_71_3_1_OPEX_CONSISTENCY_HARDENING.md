# Milestone 71.3.1 — OPEX Consistency Hardening

This patch makes the M71.3 decision layer probabilistically coherent and easier to interpret without changing the statistical settlement model or raw data inputs.

Acceptance scope:
- touch >= acceptance >= directional scenario probability;
- staged objective probabilities are monotonic and never exceed the governing scenario probability;
- current-to-target path ladder from spot through structural levels and conditional stages;
- daily path displays P25 / median / P75 bands and uses material macro-event state classification;
- magnet terminal probability mass is separated from attraction strength;
- cross-OPEX map distinguishes the current near-path decision zone from each expiration's terminal base zone;
- no schema migration; all fields are additive JSON payload fields.
