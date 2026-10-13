from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User, UserPrivacyPreferences
from app.schemas import PrivacyPreferencesRead, PrivacyPreferencesUpdate

router = APIRouter(prefix="/privacy", tags=["privacy and consent"])


@router.get("/preferences", response_model=PrivacyPreferencesRead)
def get_preferences(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PrivacyPreferencesRead:
    preferences = db.scalar(
        select(UserPrivacyPreferences).where(UserPrivacyPreferences.user_id == current_user.id)
    )
    if preferences is None:
        return PrivacyPreferencesRead()
    return PrivacyPreferencesRead.model_validate(preferences, from_attributes=True)


@router.patch("/preferences", response_model=PrivacyPreferencesRead)
def update_preferences(
    payload: PrivacyPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPrivacyPreferences:
    preferences = db.scalar(
        select(UserPrivacyPreferences).where(UserPrivacyPreferences.user_id == current_user.id)
    )
    if preferences is None:
        preferences = UserPrivacyPreferences(user_id=current_user.id)
        db.add(preferences)
    preferences.analytics_consent = payload.analytics_consent
    preferences.marketing_consent = payload.marketing_consent
    preferences.consent_version = "v1"
    db.commit()
    db.refresh(preferences)
    return preferences
