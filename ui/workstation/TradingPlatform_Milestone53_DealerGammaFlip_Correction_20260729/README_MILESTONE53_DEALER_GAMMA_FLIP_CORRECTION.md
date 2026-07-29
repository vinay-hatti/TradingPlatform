# Milestone 53 — Dealer Gamma-Flip Correction

This cumulative correction fixes two related defects:

1. The dealer-positioning engine assigned the same sign to call and put gamma, which made aggregate gamma incapable of crossing zero.
2. The Market Overview UI rendered a missing (`NULL`) gamma flip as `$0`.

The default `street_proxy` now uses opposite option-type signs and remains explicitly governed as an open-interest proxy, not observed dealer inventory. A symbol with no zero crossing in the configured 70%–130% spot grid remains `NULL` and is shown as **No flip detected**.
