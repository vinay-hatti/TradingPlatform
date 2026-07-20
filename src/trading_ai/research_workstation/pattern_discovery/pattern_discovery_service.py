from .pattern_discovery_engine import PatternDiscoveryEngine
class PatternDiscoveryService:
    def __init__(self, engine=None): self.engine=engine or PatternDiscoveryEngine()
    def build_similarity_report(self, **kwargs): return self.engine.build_similarity_report(**kwargs)
    def build_pattern_discovery(self, **kwargs): return self.engine.build_pattern_discovery(**kwargs)
