from datetime import date
from typing import Optional

from db.init_db import get_connection, init_db
from agents.models import CreditCardStatement


def save_statement(statement: CreditCardStatement) -> int:
    """
    Save a credit card statement and all its transactions to the database.

    Args:
        statement: The CreditCardStatement Pydantic model to save

    Returns:
        The ID of the inserted statement
    """
    conn = get_connection()
    cursor = conn.cursor()

    summary = statement.summary

    cursor.execute("""
        INSERT INTO statements (
            account_holder, card_number_masked, card_type,
            cut_off_date, payment_due_date,
            previous_balance_gtq, purchases_gtq, payments_gtq,
            purchases_usd, payments_usd,
            current_balance_gtq, previous_balance_usd, current_balance_usd,
            credit_limit_gtq, available_credit_gtq,
            minimum_payment_gtq, annual_interest_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        summary.account_holder,
        summary.card_number_masked,
        summary.card_type,
        str(summary.cut_off_date),
        str(summary.payment_due_date),
        float(summary.previous_balance_gtq),
        float(summary.purchases_gtq),
        float(summary.payments_gtq),
        float(summary.purchases_usd),
        float(summary.payments_usd),
        float(summary.current_balance_gtq),
        float(summary.previous_balance_usd) if summary.previous_balance_usd else None,
        float(summary.current_balance_usd) if summary.current_balance_usd else None,
        float(summary.credit_limit_gtq),
        float(summary.available_credit_gtq),
        float(summary.minimum_payment_gtq),
        float(summary.annual_interest_rate),
    ))

    statement_id = cursor.lastrowid

    for txn in statement.transactions:
        cursor.execute("""
            INSERT INTO transactions (
                statement_id, operation_date, consumption_date,
                description, amount, currency,
                transaction_type, credit_card_reference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            statement_id,
            str(txn.operation_date),
            str(txn.consumption_date),
            txn.description,
            float(txn.amount),
            txn.currency,
            txn.transaction_type,
            txn.credit_card_reference,
        ))

    conn.commit()
    conn.close()
    return statement_id


def statement_exists(card_number_masked: str, cut_off_date: date) -> bool:
    """Check if a statement already exists (to avoid duplicates)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1 FROM statements
        WHERE card_number_masked = ? AND cut_off_date = ?
    """, (card_number_masked, str(cut_off_date)))

    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_statement(statement_id: int) -> Optional[dict]:
    """Fetch a statement by ID with all its transactions."""
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM statements WHERE id = ?", (statement_id,))
    statement = cursor.fetchone()

    if not statement:
        conn.close()
        return None

    cursor.execute("SELECT * FROM transactions WHERE statement_id = ?", (statement_id,))
    transactions = cursor.fetchall()

    conn.close()
    return {
        "summary": statement,
        "transactions": transactions
    }


def get_all_statements() -> list[dict]:
    """List all statements (without transactions for performance)."""
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, account_holder, card_number_masked, card_type,
               cut_off_date, current_balance_gtq, created_at
        FROM statements
        ORDER BY cut_off_date DESC
    """)

    statements = cursor.fetchall()
    conn.close()
    return statements
