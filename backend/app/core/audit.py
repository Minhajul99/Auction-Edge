"""
Audit logging helper. Reused across UC1 (bid placed), UC3 (bid retracted),
and UC5 (auction closed) so every state-changing action gets a consistent
audit trail entry, per the client's "full audit logging" requirement.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLogEntry


def log_action(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    ip_address: Optional[str] = None,
) -> AuditLogEntry:
    """
    action examples: "bid_placed", "bid_retracted", "auction_closed",
    "auction_created", "user_registered".
    entity_type/entity_id: the record this action is about (e.g. "Bid", bid.id).

    Does not commit — caller commits as part of the same transaction as the
    triggering action, so the log entry and the state change are atomic.
    """
    entry = AuditLogEntry(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        timestamp=datetime.now(timezone.utc),
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(entry)
    return entry
