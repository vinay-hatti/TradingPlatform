from dataclasses import dataclass


@dataclass
class Container:
    """
    Very lightweight DI container for Milestone 1.
    Will evolve into full dependency graph manager later.
    """

    config: object = None
    provider: object = None
    market_service: object = None
    feature_pipeline: object = None
    decision_engine: object = None
    scanner: object = None

    def wire(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

        return self
