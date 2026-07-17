from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallet import WalletOut, DepositRequest

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/me", response_model=WalletOut)
def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    return wallet


@router.post("/deposit", response_model=WalletOut)
def deposit(
    body: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Demo-only top-up — no real payment gateway. Exists purely so you can
    fund test accounts for wallet/hold testing without a manual DB edit.
    """
    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    wallet.balance = wallet.balance + body.amount
    db.commit()
    db.refresh(wallet)
    return wallet
