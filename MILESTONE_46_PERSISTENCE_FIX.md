# Milestone 46 Persistence Scalar Fix

Fixes PostgreSQL `InvalidSchemaName: schema "np" does not exist` during Market Intelligence persistence.

Root cause: NumPy scalar values such as `np.float64(47.5)` reached SQLAlchemy text bindings. PostgreSQL interpreted the rendered expression as a schema-qualified name.

The replacement service now:

- recursively converts NumPy and Pandas scalar values to native Python types;
- normalizes nested dictionaries and lists before JSON serialization;
- converts non-finite floating-point values to `NULL`;
- applies normalization to correlation, sector, sentiment, dealer, risk, and opportunity SQL parameters;
- serializes JSON with strict `allow_nan=False`.
