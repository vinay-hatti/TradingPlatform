from .institutional_service import InstitutionalEventIntelligenceService
class GovernedExpectedMoveService(InstitutionalEventIntelligenceService):
 def __init__(self,session_factory,policy=None):super().__init__(session_factory);self.policy=policy
