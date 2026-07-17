import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    auction_id: Optional[uuid.UUID]
    type: str
    read: bool
    sent_at: datetime
