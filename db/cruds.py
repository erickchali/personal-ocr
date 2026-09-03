from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from db.database import SessionLocal
from db.models import StatementModel, TransactionModel
from db.schemas import (
    MetricsResponse,
    MonthlySpend,
    StatementDetailResponse,
    StatementListItem,
    StatementSummaryResponse,
    TransactionResponse,
)
from domain.models import CreditCardStatement


class DuplicateStatementError(Exception):
    """A statement with the same card + cut-off date (or file hash) is already stored.

    Carries the existing row so callers can report it instead of failing.
    """

    def __init__(self, statement_id: int, status: str):
        self.statement_id = statement_id
        self.status = status
        super().__init__(f"Statement {statement_id} already exists")


def save_statement(
    statement: CreditCardStatement,
    *,
    object_key: str | None = None,
    file_sha256: str | None = None,
) -> int:
    """Save a credit card statement and all its transactions to the database.

    Raises DuplicateStatementError if it collides with an existing row. The uq_statement
    constraint is the only real guard: callers check first, but those checks run in a
    separate session, so a concurrent insert can still land in between.
    """
    with SessionLocal() as session:
        summary = statement.summary

        db_statement = StatementModel(
            account_holder=summary.account_holder,
            card_number_masked=summary.card_number_masked,
            card_type=summary.card_type,
            cut_off_date=summary.cut_off_date,
            payment_due_date=summary.payment_due_date,
            previous_balance_gtq=float(summary.previous_balance_gtq),
            purchases_gtq=float(summary.purchases_gtq),
            payments_gtq=float(summary.payments_gtq),
            purchases_usd=float(summary.purchases_usd),
            payments_usd=float(summary.payments_usd),
            current_balance_gtq=float(summary.current_balance_gtq),
            previous_balance_usd=(float(summary.previous_balance_usd) if summary.previous_balance_usd else None),
            current_balance_usd=(float(summary.current_balance_usd) if summary.current_balance_usd else None),
            credit_limit_gtq=float(summary.credit_limit_gtq),
            available_credit_gtq=float(summary.available_credit_gtq),
            minimum_payment_gtq=float(summary.minimum_payment_gtq),
            annual_interest_rate=float(summary.annual_interest_rate),
            object_key=object_key,
            file_sha256=file_sha256,
        )

        for txn in statement.transactions:
            db_txn = TransactionModel(
                operation_date=txn.operation_date,
                consumption_date=txn.consumption_date,
                description=txn.description,
                amount=float(txn.amount),
                currency=txn.currency,
                transaction_type=txn.transaction_type,
                credit_card_reference=txn.credit_card_reference,
            )
            db_statement.transactions.append(db_txn)

        session.add(db_statement)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            existing = _find_duplicate(session, summary.card_number_masked, summary.cut_off_date, file_sha256)
            if existing is None:
                raise
            raise DuplicateStatementError(existing.id, existing.status) from exc

        session.refresh(db_statement)
        return db_statement.id


def _find_duplicate(session, card_number_masked: str, cut_off_date: date, file_sha256: str | None):
    """Locate the row that caused an IntegrityError — either constraint may have fired."""
    clauses = [
        (StatementModel.card_number_masked == card_number_masked) & (StatementModel.cut_off_date == cut_off_date)
    ]
    if file_sha256:
        clauses.append(StatementModel.file_sha256 == file_sha256)

    for clause in clauses:
        found = session.execute(select(StatementModel).where(clause)).scalar_one_or_none()
        if found:
            return found
    return None


def statement_exists(card_number_masked: str, cut_off_date: date) -> bool:
    """Check if a statement already exists (to avoid duplicates)."""
    with SessionLocal() as session:
        stmt = select(StatementModel).where(
            StatementModel.card_number_masked == card_number_masked,
            StatementModel.cut_off_date == cut_off_date,
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
        transactions = [TransactionResponse.model_validate(txn) for txn in db_statement.transactions]

        return StatementDetailResponse(summary=summary, transactions=transactions)


def get_all_statements(status: str | None = None) -> list[StatementListItem]:
    """List all statements (without transactions for performance)."""
    with SessionLocal() as session:
        stmt = select(StatementModel).order_by(StatementModel.cut_off_date.desc())
        if status:
            stmt = stmt.where(StatementModel.status == status)
        results = session.execute(stmt).scalars().all()

        return [StatementListItem.model_validate(s) for s in results]


def get_metrics() -> MetricsResponse:
    """Dashboard aggregates.

    Uses extract() rather than to_char()/strftime() for the month grouping so the same
    query runs on Postgres and on the SQLite test database.
    """
    with SessionLocal() as session:
        purchases = _amount_total(session, "purchase")
        payments = _amount_total(session, "payment")

        year = func.extract("year", TransactionModel.consumption_date)
        month = func.extract("month", TransactionModel.consumption_date)
        rows = session.execute(
            select(year, month, func.sum(TransactionModel.amount), func.count(TransactionModel.id))
            .where(TransactionModel.currency == "GTQ", TransactionModel.transaction_type == "purchase")
            .group_by(year, month)
            .order_by(year, month)
        ).all()

        return MetricsResponse(
            statement_count=session.execute(select(func.count(StatementModel.id))).scalar_one(),
            transaction_count=session.execute(select(func.count(TransactionModel.id))).scalar_one(),
            pending_count=session.execute(
                select(func.count(StatementModel.id)).where(StatementModel.status == "pending")
            ).scalar_one(),
            total_purchases_gtq=purchases,
            total_payments_gtq=payments,
            latest_cut_off_date=session.execute(select(func.max(StatementModel.cut_off_date))).scalar_one(),
            spend_by_month=[
                MonthlySpend(month=f"{int(y):04d}-{int(m):02d}", total_gtq=float(total), transaction_count=count)
                for y, m, total, count in rows
            ],
        )


def _amount_total(session, transaction_type: str) -> float:
    stmt = select(func.coalesce(func.sum(TransactionModel.amount), 0.0)).where(
        TransactionModel.currency == "GTQ",
        TransactionModel.transaction_type == transaction_type,
    )
    return float(session.execute(stmt).scalar_one())


def statement_by_hash(file_sha256: str) -> StatementListItem | None:
    """Look up a statement by its source file hash.

    The cheap rung of the idempotency ladder — runs before extraction, so a byte-identical
    re-upload never reaches the LLM.
    """
    with SessionLocal() as session:
        stmt = select(StatementModel).where(StatementModel.file_sha256 == file_sha256)
        found = session.execute(stmt).scalar_one_or_none()
        return StatementListItem.model_validate(found) if found else None


def attach_source(statement_id: int, object_key: str, file_sha256: str) -> bool:
    """Record where a statement came from, if it has no source recorded yet.

    Lets an upload that turned out to duplicate an existing statement teach that row its
    file hash, so the *next* upload of the same bytes short-circuits before extraction
    rather than paying for it again. Never overwrites a hash already present.
    """
    with SessionLocal() as session:
        found = session.execute(select(StatementModel).where(StatementModel.id == statement_id)).scalar_one_or_none()
        if not found or found.file_sha256:
            return False

        found.object_key = object_key
        found.file_sha256 = file_sha256
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return False
        return True


def approve_statement(statement_id: int) -> StatementListItem | None:
    """Mark a pending statement as approved. The async equivalent of resuming an interrupt."""
    with SessionLocal() as session:
        stmt = select(StatementModel).where(StatementModel.id == statement_id)
        found = session.execute(stmt).scalar_one_or_none()
        if not found:
            return None

        found.status = "approved"
        session.commit()
        session.refresh(found)
        return StatementListItem.model_validate(found)
