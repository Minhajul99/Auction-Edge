import uuid
from sqlalchemy import Column, String, Text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)  # closed enum: Gaming, Photography, Audio, Computers
    photos = Column(ARRAY(String), default=list)  # list of photo URLs

    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    seller = relationship("User", back_populates="items")
    auctions = relationship("Auction", back_populates="item")  # 1:many, supports relisting