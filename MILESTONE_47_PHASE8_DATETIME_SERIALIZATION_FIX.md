# Milestone 47 Phase 8 — Datetime Serialization Fix

## Issue

`run_m47_end_to_end_certification.py` completed its certification checks but failed while writing `milestone47_certification_manifest.json` when database-backed metadata contained Python `datetime` objects.

## Root cause

The certification JSON and HTML exporters normalized temporal values, but `write_report_manifest()` passed the manifest `metadata` payload directly to `json.dumps()`.

## Fix

The shared manifest writer now recursively converts these values to JSON-native representations:

- `datetime`, `date`, and `time` to ISO-8601 strings
- `Decimal` to a number
- `UUID`, `Path`, and `Enum` to strings
- dataclasses, mappings, and nested collections recursively
- NumPy/Pandas scalar-like values through their `item()` representation
- unknown residual objects to strings as a safe final fallback

This fixes certification and protects all scanner, decision, replay, and future report manifests.

## Validation

All Milestone 47 Phase 1–8 tests and Python compile validation pass. The Phase 8 test now includes database-style `datetime`, `date`, `Decimal`, and nested datetime metadata.
