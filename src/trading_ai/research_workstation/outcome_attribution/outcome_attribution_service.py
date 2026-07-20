from .outcome_attribution_engine import OutcomeAttributionEngine
class OutcomeAttributionService:
    def __init__(self,engine=None): self.engine=engine or OutcomeAttributionEngine()
    def evaluate(self,**kwargs): return self.engine.evaluate(**kwargs)
