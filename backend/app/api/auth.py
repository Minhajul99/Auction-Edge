from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.user import UserCreate, UserOut
from app.core.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        email_verified=False,
        roles=["seller", "bidder"],
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Demo wallet — no real payment gateway, seeded with a starting balance
    # purely so bid-hold logic has funds to work with immediately.
    wallet = Wallet(user_id=db_user.id)  # balance defaults to 1000.00
    db.add(wallet)
    db.commit()

    token = create_access_token(db_user.id)
    return TokenResponse(access_token=token, user=db_user)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Uses OAuth2PasswordRequestForm so this also works directly in Swagger's
    'Authorize' button. form_data.username is treated as the email.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user)
