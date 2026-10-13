from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models import Notification, PushSubscription, User
from app.schemas import NotificationRead, PushPublicKeyRead, PushSubscriptionCreate, PushSubscriptionRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=list[NotificationRead])
def list_my_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100)
    return list(db.scalars(query))


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot access another member's notification")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


@router.post("/me/read-all", status_code=204)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    db.commit()


@router.get("/push/public-key", response_model=PushPublicKeyRead)
def get_push_public_key(_: User = Depends(get_current_user)) -> dict:
    enabled = bool(settings.vapid_public_key and settings.vapid_private_key and settings.vapid_claims_email)
    return {"enabled": enabled, "public_key": settings.vapid_public_key if enabled else None}


@router.post("/push/subscriptions", response_model=PushSubscriptionRead, status_code=201)
def create_push_subscription(
    payload: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PushSubscription:
    if not (settings.vapid_public_key and settings.vapid_private_key and settings.vapid_claims_email):
        raise HTTPException(status_code=503, detail="Browser push is not configured. In-app class reminders remain available.")
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint))
    if existing is not None and existing.user_id != current_user.id:
        raise HTTPException(status_code=409, detail="This browser push endpoint is already registered to another account")
    if existing is None:
        existing = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh=payload.p256dh,
            auth=payload.auth,
        )
        db.add(existing)
    else:
        existing.p256dh = payload.p256dh
        existing.auth = payload.auth
    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/push/subscriptions/{subscription_id}", status_code=204)
def delete_push_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    subscription = db.get(PushSubscription, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Push subscription not found")
    if subscription.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot remove another user's push subscription")
    db.delete(subscription)
    db.commit()


@router.get("/push/subscriptions/me", response_model=list[PushSubscriptionRead])
def list_my_push_subscriptions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PushSubscription]:
    return list(db.scalars(select(PushSubscription).where(
        PushSubscription.user_id == current_user.id
    ).order_by(PushSubscription.created_at.desc()).limit(20)))
