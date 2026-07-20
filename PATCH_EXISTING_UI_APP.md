# Optional existing UI registration

Add to `src/trading_ai/ui/app.py`:

```python
from trading_ai.ui.api.research_scanner import router as research_scanner_router
app.include_router(research_scanner_router)
```

The standalone launcher does not require this patch.
