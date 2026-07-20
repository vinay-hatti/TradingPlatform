from typing import Any
from .institutional_learning_engine import InstitutionalLearningEngine
class InstitutionalLearningService:
    def __init__(self, engine: InstitutionalLearningEngine|None=None): self.engine=engine or InstitutionalLearningEngine()
    def build(self, **kwargs: Any): return self.engine.build(**kwargs)
