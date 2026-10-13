from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.notifications import add_notification
from app.models import SupportTicket, User
from app.schemas import SupportTicketCreate, SupportTicketRead, SupportTicketStatusUpdate

router = APIRouter(prefix="/support/tickets", tags=["support"])
ALLOWED_TICKET_TRANSITIONS = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"open", "resolved", "closed"},
    "resolved": {"open", "closed"},
    "closed": set(),
}


@router.post("", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportTicket:
    ticket = SupportTicket(user_id=current_user.id, **payload.model_dump())
    db.add(ticket)
    db.flush()
    add_notification(
        db, current_user.id, "Support request received",
        f"Request #{ticket.id} has been created. You can track its status in Help & Support.",
        "support",
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/me", response_model=list[SupportTicketRead])
def list_my_tickets(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SupportTicket]:
    return list(db.scalars(
        select(SupportTicket).where(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.created_at.desc()).limit(100)
    ))


@router.get("", response_model=list[SupportTicketRead])
def list_all_tickets(
    db: Session = Depends(get_db), _: User = Depends(require_roles("staff", "admin"))
) -> list[SupportTicket]:
    return list(db.scalars(select(SupportTicket).order_by(SupportTicket.created_at.asc()).limit(500)))


@router.patch("/{ticket_id}", response_model=SupportTicketRead)
def update_ticket(
    ticket_id: int,
    payload: SupportTicketStatusUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_roles("staff", "admin")),
) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if payload.status != ticket.status and payload.status not in ALLOWED_TICKET_TRANSITIONS[ticket.status]:
        raise HTTPException(status_code=409, detail=f"Invalid ticket status transition: {ticket.status} -> {payload.status}")
    ticket.status = payload.status
    if payload.staff_response is not None:
        ticket.staff_response = payload.staff_response
    if payload.status in {"resolved", "closed"}:
        ticket.resolved_at = ticket.resolved_at or datetime.now(timezone.utc)
    else:
        ticket.resolved_at = None
    add_notification(
        db, ticket.user_id, "Support request updated",
        (f"Request #{ticket.id} status: {ticket.status.replace('_', ' ')}."
         + (f" Staff response: {ticket.staff_response}" if ticket.staff_response else ""))[:500],
        "support",
    )
    db.commit()
    db.refresh(ticket)
    return ticket
