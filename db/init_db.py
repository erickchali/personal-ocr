import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "statements.db"


def init_db() -> sqlite3.Connection:
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_holder TEXT NOT NULL,
            card_number_masked TEXT NOT NULL,
            card_type TEXT,
            cut_off_date TEXT NOT NULL,
            payment_due_date TEXT,
            previous_balance_gtq REAL,
            purchases_gtq REAL,
            payments_gtq REAL,
            purchases_usd REAL,
            payments_usd REAL,
            current_balance_gtq REAL,
            previous_balance_usd REAL,
            current_balance_usd REAL,
            credit_limit_gtq REAL,
            available_credit_gtq REAL,
            minimum_payment_gtq REAL,
            annual_interest_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id INTEGER NOT NULL,
            operation_date TEXT NOT NULL,
            consumption_date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            credit_card_reference TEXT,
            FOREIGN KEY (statement_id) REFERENCES statements(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_statement_id
        ON transactions(statement_id)
    """)

    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_statements_unique
        ON statements(card_number_masked, cut_off_date)
    """)

    conn.commit()
    return conn


def get_connection() -> sqlite3.Connection:
    """Get a database connection, initializing if needed."""
    if not DB_PATH.exists():
        return init_db()
    return sqlite3.connect(DB_PATH)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
