"""Scheduled maintenance task; invoke at least once per minute for class reminders."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.class_reminders import process_due_class_reminders
from app.core.clock import business_today
from app.core.database import SessionLocal
from app.core.notifications import add_notification
from app.models import Membership


def process_due_membership_resumes(db: Session, today: date | None = None) -> int:
    """Complete scheduled freezes and extend expiry by the exact scheduled freeze duration."""
    today = today or business_today()
    due = list(db.scalars(select(Membership).where(
        Membership.status == "frozen",
        Membership.freeze_start_date.is_not(None),
        Membership.freeze_until_date.is_not(None),
        Membership.freeze_until_date <= today,
    ).with_for_update()))
    for membership in due:
        planned_days = max((membership.freeze_until_date - membership.freeze_start_date).days, 0)
        membership.expiry_date += timedelta(days=planned_days)
        membership.status = "active" if membership.expiry_date >= today else "expired"
        membership.freeze_start_date = None
        membership.freeze_until_date = None
        add_notification(
            db, membership.user_id, "Membership resumed automatically",
            f"Your scheduled membership freeze ended. Your membership is {membership.status}; new expiry date: {membership.expiry_date}.",
            "membership",
        )
    db.commit()
    return len(due)


def run_scheduled_tasks(db: Session) -> dict[str, int]:
    return {
        "class_reminders_processed": process_due_class_reminders(db),
        "membership_freezes_resumed": process_due_membership_resumes(db),
    }


if __name__ == "__main__":
    with SessionLocal() as session:
        results = run_scheduled_tasks(session)
        print(results)
