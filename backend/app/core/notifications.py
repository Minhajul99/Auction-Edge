"""
UC6: Notification creation helper.

Kept as a thin, reusable function so UC1 (outbid), UC2 (reserve met),
and UC5 (auction closed/won/unsold) all create notifications the same way,
instead of duplicating insert logic in every endpoint.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    auction_id: uuid.UUID | None,
    notification_type: str,
) -> Notification:
    """
    notification_type examples: "outbid", "reserve_met", "won", "unsold",
    "unsold_reserve_not_met", "seller_new_bid", "seller_auction_closed".

    Does not commit — caller is expected to commit as part of the same
    transaction as the triggering action (bid placement, auction close, etc.)
    so the notification and the state change are atomic together.
    """
    notification = Notification(
        user_id=user_id,
        auction_id=auction_id,
        type=notification_type,
        read=False,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    return notification
