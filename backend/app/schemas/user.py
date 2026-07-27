import uuid
from typing import List, Optional
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
    avatar: Optional[str] = None
    # NOTE: password_hash is intentionally excluded — never returned to client


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_blank_if_given(cls, v):
        if v is not None and not v.strip():
            raise ValueError("This field cannot be blank.")
        return v.strip() if v is not None else v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("A new password is required.")
        return v