from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.models import (
    CreditCardStatement,
    StatementSummary,
    Transaction,
)
from db.models import Base

TEST_DB_PATH = Path(__file__).parent / "test_statements.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


@pytest.fixture(autouse=True)
def test_db():
    """Create a fresh SQLite test database for each test, tear down after."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine)

    with patch("db.cruds.SessionLocal", test_session_local):
        yield test_session_local

    Base.metadata.drop_all(engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def sample_statement() -> CreditCardStatement:
    """A realistic credit card statement for testing."""
    return CreditCardStatement(
        summary=StatementSummary(
            account_holder="Juan Perez",
            card_number_masked="XXXX XXXX XXXX 1075",
            card_type="SIGNATURE",
            cut_off_date=date(2025, 3, 15),
            payment_due_date=date(2025, 4, 5),
            previous_balance_gtq=Decimal("5000.00"),
            purchases_gtq=Decimal("1200.50"),
            payments_gtq=Decimal("3000.00"),
            purchases_usd=Decimal("150.00"),
            payments_usd=Decimal("0.00"),
            current_balance_gtq=Decimal("3200.50"),
            previous_balance_usd=Decimal("200.00"),
            current_balance_usd=Decimal("350.00"),
            credit_limit_gtq=Decimal("25000.00"),
            available_credit_gtq=Decimal("21799.50"),
            minimum_payment_gtq=Decimal("640.10"),
            annual_interest_rate=Decimal("24.00"),
        ),
        transactions=[
            Transaction(
                operation_date=date(2025, 3, 1),
                consumption_date=date(2025, 3, 1),
                description="AMAZON MKTPLACE PMTS",
                amount=Decimal("450.00"),
                currency="GTQ",
                transaction_type="purchase",
                credit_card_reference="XXXXXX 1075",
            ),
            Transaction(
                operation_date=date(2025, 3, 5),
                consumption_date=date(2025, 3, 5),
                description="UBER EATS",
                amount=Decimal("120.50"),
                currency="GTQ",
                transaction_type="purchase",
                credit_card_reference="XXXXXX 1075",
            ),
            Transaction(
                operation_date=date(2025, 3, 10),
                consumption_date=date(2025, 3, 10),
                description="PAGO EN LINEA",
                amount=Decimal("3000.00"),
                currency="GTQ",
                transaction_type="payment",
                credit_card_reference="XXXXXX 1075",
            ),
        ],
    )


@pytest.fixture
def second_statement() -> CreditCardStatement:
    """A second statement with different card/date for multi-statement tests."""
    return CreditCardStatement(
        summary=StatementSummary(
            account_holder="Juan Perez",
            card_number_masked="XXXX XXXX XXXX 3251",
            card_type="MC BLACK",
            cut_off_date=date(2025, 3, 20),
            payment_due_date=date(2025, 4, 10),
            previous_balance_gtq=Decimal("10000.00"),
            purchases_gtq=Decimal("2500.00"),
            payments_gtq=Decimal("5000.00"),
            purchases_usd=Decimal("0.00"),
            payments_usd=Decimal("0.00"),
            current_balance_gtq=Decimal("7500.00"),
            credit_limit_gtq=Decimal("50000.00"),
            available_credit_gtq=Decimal("42500.00"),
            minimum_payment_gtq=Decimal("1500.00"),
            annual_interest_rate=Decimal("18.00"),
        ),
        transactions=[
            Transaction(
                operation_date=date(2025, 3, 12),
                consumption_date=date(2025, 3, 12),
                description="WALMART SUPERCENTER",
                amount=Decimal("2500.00"),
                currency="GTQ",
                transaction_type="purchase",
                credit_card_reference="XXXXXX 3251",
            ),
        ],
    )
