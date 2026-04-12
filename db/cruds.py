from datetime import date

from sqlalchemy import select

from agents.models import CreditCardStatement
from db.database import SessionLocal
from db.models import StatementModel, TransactionModel
from db.schemas import (
    StatementDetailResponse,
    StatementListItem,
    StatementSummaryResponse,
    TransactionResponse,
)


def save_statement(statement: CreditCardStatement) -> int:
    """Save a credit card statement and all its transactions to the database."""
    with SessionLocal() as session:
        summary = statement.summary

        db_statement = StatementModel(
            account_holder=summary.account_holder,
            card_number_masked=summary.card_number_masked,
            card_type=summary.card_type,
            cut_off_date=str(summary.cut_off_date),
            payment_due_date=str(summary.payment_due_date),
            previous_balance_gtq=float(summary.previous_balance_gtq),
            purchases_gtq=float(summary.purchases_gtq),
            payments_gtq=float(summary.payments_gtq),
            purchases_usd=float(summary.purchases_usd),
            payments_usd=float(summary.payments_usd),
            current_balance_gtq=float(summary.current_balance_gtq),
            previous_balance_usd=(
                float(summary.previous_balance_usd) if summary.previous_balance_usd else None
            ),
            current_balance_usd=(
                float(summary.current_balance_usd) if summary.current_balance_usd else None
            ),
            credit_limit_gtq=float(summary.credit_limit_gtq),
            available_credit_gtq=float(summary.available_credit_gtq),
            minimum_payment_gtq=float(summary.minimum_payment_gtq),
            annual_interest_rate=float(summary.annual_interest_rate),
        )

        for txn in statement.transactions:
            db_txn = TransactionModel(
                operation_date=str(txn.operation_date),
                consumption_date=str(txn.consumption_date),
                description=txn.description,
                amount=float(txn.amount),
                currency=txn.currency,
                transaction_type=txn.transaction_type,
                credit_card_reference=txn.credit_card_reference,
            )
            db_statement.transactions.append(db_txn)

        session.add(db_statement)
        session.commit()
        session.refresh(db_statement)
        return db_statement.id


def statement_exists(card_number_masked: str, cut_off_date: date) -> bool:
    """Check if a statement already exists (to avoid duplicates)."""
    with SessionLocal() as session:
        stmt = select(StatementModel).where(
            StatementModel.card_number_masked == card_number_masked,
            StatementModel.cut_off_date == str(cut_off_date),
        )
        result = session.execute(stmt).scalar_one_or_none()
        return result is not None


def get_statement(statement_id: int) -> StatementDetailResponse | None:
    """Fetch a statement by ID with all its transactions."""
    with SessionLocal() as session:
        stmt = select(StatementModel).where(StatementModel.id == statement_id)
        db_statement = session.execute(stmt).scalar_one_or_none()

        if not db_statement:
            return None

        summary = StatementSummaryResponse.model_validate(db_statement)
        transactions = [
            TransactionResponse.model_validate(txn) for txn in db_statement.transactions
        ]

        return StatementDetailResponse(summary=summary, transactions=transactions)


def get_all_statements() -> list[StatementListItem]:
    """List all statements (without transactions for performance)."""
    with SessionLocal() as session:
        stmt = select(StatementModel).order_by(StatementModel.cut_off_date.desc())
        results = session.execute(stmt).scalars().all()

        return [StatementListItem.model_validate(s) for s in results]
