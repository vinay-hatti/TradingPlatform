from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.professional_order_entry import (
    ApprovalRequest,
    StrategyTicketRequest,
    SubmissionRequest,
)
from trading_ai.ui.services.professional_order_entry_service import (
    ProfessionalOrderEntryService,
)

router = APIRouter(prefix="/api/v1/professional-orders", tags=["professional-orders"])


def service():
    return ProfessionalOrderEntryService()


@router.post("/preview")
def preview(request: StrategyTicketRequest, svc=Depends(service)):
    return svc.preview(request)


@router.post("/tickets")
def create_ticket(request: StrategyTicketRequest, svc=Depends(service)):
    return svc.create(request)


@router.get("/tickets")
def list_tickets(svc=Depends(service)):
    return svc.list()


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, svc=Depends(service)):
    try:
        return svc.get(ticket_id)
    except KeyError:
        raise HTTPException(404, "Ticket not found")


@router.post("/tickets/{ticket_id}/approval")
def approve(ticket_id: str, request: ApprovalRequest, svc=Depends(service)):
    try:
        return svc.approve(ticket_id, request)
    except KeyError:
        raise HTTPException(404, "Ticket not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))


@router.post("/tickets/{ticket_id}/submit")
def submit(ticket_id: str, request: SubmissionRequest, svc=Depends(service)):
    try:
        return svc.submit(ticket_id, request)
    except KeyError:
        raise HTTPException(404, "Ticket not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))
