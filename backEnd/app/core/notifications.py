from app.models import Notification
from sqlalchemy.orm import Session


def add_notification(db: Session, user_id: int, title: str, body: str, category: str = "general") -> None:
    db.add(Notification(user_id=user_id, title=title, body=body, category=category))
