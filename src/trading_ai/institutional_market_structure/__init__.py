from .contracts import DealerPositioningPolicy, InstitutionalMarketStructureSnapshot
from .engine import InstitutionalMarketStructureEngine

__all__=["DealerPositioningPolicy","InstitutionalMarketStructureSnapshot","InstitutionalMarketStructureEngine","InstitutionalMarketStructureService","scanner_context"]

def __getattr__(name: str):
    if name == "InstitutionalMarketStructureService":
        from .service import InstitutionalMarketStructureService
        return InstitutionalMarketStructureService
    raise AttributeError(name)


def scanner_context(*args, **kwargs):
    from .integration import scanner_context as _scanner_context
    return _scanner_context(*args, **kwargs)
