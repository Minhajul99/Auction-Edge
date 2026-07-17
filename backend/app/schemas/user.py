import uuid
from typing import List
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str  # plain password from client; hashed before storage

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("This field is required.")
        return v.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    email_verified: bool
    roles: List[str]
    # NOTE: password_hash is intentionally excluded — never returned to client