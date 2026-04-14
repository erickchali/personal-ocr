"""Response schemas for the DB layer.

These Pydantic models define the shape of data returned by cruds.py.
They are the interface between the database and the rest of the app
(graph nodes, tools, future API endpoints).
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement_id: int
    operation_date: date
    consumption_date: date
    description: str
    amount: float
    currency: str
    transaction_type: str
    credit_card_reference: str | None = None


class StatementSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_holder: str
    card_number_masked: str
    card_type: str | None = None
    cut_off_date: date
    payment_due_date: date | None = None
    previous_balance_gtq: float | None = None
    purchases_gtq: float | None = None
    payments_gtq: float | None = None
    purchases_usd: float | None = None
    payments_usd: float | None = None
    current_balance_gtq: float | None = None
    previous_balance_usd: float | None = None
    current_balance_usd: float | None = None
    credit_limit_gtq: float | None = None
    available_credit_gtq: float | None = None
    minimum_payment_gtq: float | None = None
    annual_interest_rate: float | None = None
    created_at: datetime | None = None


class StatementDetailResponse(BaseModel):
    summary: StatementSummaryResponse
    transactions: list[TransactionResponse]


class StatementListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_holder: str
    card_number_masked: str
    card_type: str | None = None
    cut_off_date: date
    current_balance_gtq: float | None = None
    created_at: datetime | None = None
