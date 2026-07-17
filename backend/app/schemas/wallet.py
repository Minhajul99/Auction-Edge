from decimal import Decimal
from pydantic import BaseModel, ConfigDict, computed_field, field_validator


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    balance: Decimal
    held_amount: Decimal

    @computed_field
    @property
    def available(self) -> Decimal:
        return self.balance - self.held_amount


class DepositRequest(BaseModel):
    """Demo-only top-up — no real payment gateway."""
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Deposit amount must be positive.")
        return v
