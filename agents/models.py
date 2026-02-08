"""
Pydantic models for credit card statement extraction.

WHY PYDANTIC?
- Validation: Ensures LLM output matches expected schema
- Type hints: IDE autocomplete + runtime checks
- Serialization: .model_dump() gives you a dict, .model_dump_json() gives JSON
- Field descriptions: Help the LLM understand what each field should contain
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional

from langchain.agents import AgentState
from pydantic import BaseModel, Field, BeforeValidator


def parse_guatemalan_date(value: str | date) -> date:
    """Parse date from dd/mm/yy, dd/mm/yyyy, or YYYY-MM-DD format."""
    if isinstance(value, date):
        return value

    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date '{value}'")


GuatemalanDate = Annotated[date, BeforeValidator(parse_guatemalan_date)]


class OCRCustomState(AgentState):
    files_to_process: Optional[list[str]] = []


class Currency(str, Enum):
    """
    Using an Enum ensures the LLM can only output valid currency codes.
    This prevents hallucinated currencies like "EUR" when we only have Q and USD.
    """
    GTQ = "GTQ"  # Guatemalan Quetzal
    USD = "USD"  # US Dollar


class TransactionType(str, Enum):
    """
    Categorize transactions for easier analysis later.
    """
    PURCHASE = "purchase"
    PAYMENT = "payment"
    INSTALLMENT = "installment"
    CREDIT = "credit"
    FEE = "fee"
    INTEREST = "interest"


class Transaction(BaseModel):
    operation_date: GuatemalanDate = Field(
        description="Date when the bank processed the transaction (Fecha de operación)"
    )
    consumption_date: GuatemalanDate = Field(
        description="Date when the purchase was made (Fecha de consumo)"
    )
    description: str = Field(
        description="Merchant name or transaction description"
    )
    amount: Decimal = Field(
        description="Transaction amount (always positive)",
        gt=0  # Validation: must be greater than 0
    )
    currency: Currency = Field(
        description="Currency: GTQ for Quetzales, USD for Dollars"
    )
    transaction_type: TransactionType = Field(
        description="Type of transaction: purchase, payment, installment, credit, fee, or interest"
    )
    credit_card_reference: Optional[str] = Field(
        default=None,
        description="Masked card number from the SUB TOTAL row (e.g., 'XXXXXX 3251'). Each transaction inherits the card reference from the subtotal row that follows its group."
    )

    class Config:
        # This makes the model work better with JSON serialization
        use_enum_values = True


class StatementSummary(BaseModel):
    account_holder: str = Field(
        description="Name of the primary account holder"
    )
    card_number_masked: str = Field(
        description="Masked card number (e.g., XXXX XXXX XXXX 1116)"
    )
    card_type: str = Field(
        description="Card type/name (e.g., MC BLACK INTERNACIONAL)"
    )

    # Dates
    cut_off_date: GuatemalanDate = Field(
        description="Statement cut-off date (Fecha de corte)"
    )
    payment_due_date: GuatemalanDate = Field(
        description="Payment due date (Fecha de pago)"
    )

    # Balances in local currency (GTQ)
    previous_balance_gtq: Decimal = Field(
        description="Previous balance in Quetzales (Saldo anterior)"
    )
    purchases_gtq: Decimal = Field(
        description="Total purchases and withdrawals in Quetzales"
    )
    payments_gtq: Decimal = Field(
        description="Total payments in Quetzales"
    )
    purchases_usd: Decimal = Field(
        description="Total purchases and withdrawals in USD ($)"
    )
    payments_usd: Decimal = Field(
        description="Total payments in USD ($)"
    )
    current_balance_gtq: Decimal = Field(
        description="Current balance in Quetzales (Saldo al corte)"
    )

    # Balances in USD (optional since not all cards have USD)
    previous_balance_usd: Optional[Decimal] = Field(
        default=None,
        description="Previous balance in USD"
    )
    current_balance_usd: Optional[Decimal] = Field(
        default=None,
        description="Current balance in USD"
    )

    # Credit info
    credit_limit_gtq: Decimal = Field(
        description="Credit limit in Quetzales"
    )
    available_credit_gtq: Decimal = Field(
        description="Available credit in Quetzales"
    )
    minimum_payment_gtq: Decimal = Field(
        description="Minimum payment due in Quetzales (Pago mínimo)"
    )

    # Interest rates
    annual_interest_rate: Decimal = Field(
        description="Annual interest rate as percentage (e.g., 24.00)"
    )


class CreditCardStatement(BaseModel):
    """
    Complete credit card statement combining summary and transactions.

    WHY THIS STRUCTURE?
    - One statement = one summary + many transactions
    - Matches the real-world document structure
    - Easy to serialize and store as a single unit
    """
    summary: StatementSummary = Field(
        description="Statement summary/header information"
    )
    transactions: list[Transaction] = Field(
        default_factory=list,
        description="List of all transactions in the statement"
    )

    def total_debits(self, currency: Currency = Currency.GTQ) -> Decimal:
        """Helper method to sum all purchases/debits."""
        return sum(
            t.amount for t in self.transactions
            if t.currency == currency and t.transaction_type == TransactionType.PURCHASE
        )

    def total_credits(self, currency: Currency = Currency.GTQ) -> Decimal:
        """Helper method to sum all payments/credits."""
        return sum(
            t.amount for t in self.transactions
            if t.currency == currency and t.transaction_type == TransactionType.PAYMENT
        )
