from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class StatementModel(Base):
    __tablename__ = "statements"
    __table_args__ = (
        UniqueConstraint("card_number_masked", "cut_off_date", name="uq_statement"),
        Index("idx_transactions_statement_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_holder: Mapped[str] = mapped_column(String, nullable=False)
    card_number_masked: Mapped[str] = mapped_column(String, nullable=False)
    card_type: Mapped[str | None] = mapped_column(String)
    cut_off_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_due_date: Mapped[date | None] = mapped_column(Date)
    previous_balance_gtq: Mapped[float | None] = mapped_column(Float)
    purchases_gtq: Mapped[float | None] = mapped_column(Float)
    payments_gtq: Mapped[float | None] = mapped_column(Float)
    purchases_usd: Mapped[float | None] = mapped_column(Float)
    payments_usd: Mapped[float | None] = mapped_column(Float)
    current_balance_gtq: Mapped[float | None] = mapped_column(Float)
    previous_balance_usd: Mapped[float | None] = mapped_column(Float)
    current_balance_usd: Mapped[float | None] = mapped_column(Float)
    credit_limit_gtq: Mapped[float | None] = mapped_column(Float)
    available_credit_gtq: Mapped[float | None] = mapped_column(Float)
    minimum_payment_gtq: Mapped[float | None] = mapped_column(Float)
    annual_interest_rate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    transactions: Mapped[list["TransactionModel"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )


class TransactionModel(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id"), nullable=False)
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    consumption_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String, nullable=False)
    credit_card_reference: Mapped[str | None] = mapped_column(String)

    statement: Mapped["StatementModel"] = relationship(back_populates="transactions")
