from db.cruds import (
    get_all_statements,
    get_statement,
    save_statement,
    statement_exists,
)
from db.schemas import StatementDetailResponse, StatementListItem


class TestSaveStatement:
    def test_returns_id(self, sample_statement):
        statement_id = save_statement(sample_statement)
        assert isinstance(statement_id, int)
        assert statement_id > 0

    def test_saves_summary_fields(self, sample_statement):
        statement_id = save_statement(sample_statement)
        result = get_statement(statement_id)

        assert result is not None
        assert result.summary.account_holder == "Juan Perez"
        assert result.summary.card_number_masked == "XXXX XXXX XXXX 1075"
        assert result.summary.card_type == "SIGNATURE"
        assert result.summary.current_balance_gtq == 3200.50

    def test_saves_transactions(self, sample_statement):
        statement_id = save_statement(sample_statement)
        result = get_statement(statement_id)

        assert result is not None
        assert len(result.transactions) == 3
        assert result.transactions[0].description == "AMAZON MKTPLACE PMTS"
        assert result.transactions[0].amount == 450.00
        assert result.transactions[1].description == "UBER EATS"
        assert result.transactions[2].transaction_type == "payment"

    def test_saves_nullable_usd_fields(self, second_statement):
        statement_id = save_statement(second_statement)
        result = get_statement(statement_id)

        assert result is not None
        assert result.summary.previous_balance_usd is None
        assert result.summary.current_balance_usd is None


class TestStatementExists:
    def test_exists_returns_true(self, sample_statement):
        save_statement(sample_statement)
        assert statement_exists("XXXX XXXX XXXX 1075", sample_statement.summary.cut_off_date)

    def test_not_exists_returns_false(self):
        assert not statement_exists("XXXX XXXX XXXX 9999", "2025-01-01")

    def test_different_card_not_duplicate(self, sample_statement, second_statement):
        save_statement(sample_statement)
        assert not statement_exists(
            second_statement.summary.card_number_masked,
            second_statement.summary.cut_off_date,
        )


class TestGetStatement:
    def test_returns_detail_response(self, sample_statement):
        statement_id = save_statement(sample_statement)
        result = get_statement(statement_id)

        assert isinstance(result, StatementDetailResponse)

    def test_not_found_returns_none(self):
        result = get_statement(99999)
        assert result is None

    def test_transactions_linked_to_statement(self, sample_statement):
        statement_id = save_statement(sample_statement)
        result = get_statement(statement_id)

        assert result is not None
        for txn in result.transactions:
            assert txn.statement_id == statement_id


class TestGetAllStatements:
    def test_empty_db_returns_empty_list(self):
        result = get_all_statements()
        assert result == []

    def test_returns_list_items(self, sample_statement):
        save_statement(sample_statement)
        result = get_all_statements()

        assert len(result) == 1
        assert isinstance(result[0], StatementListItem)
        assert result[0].card_number_masked == "XXXX XXXX XXXX 1075"

    def test_multiple_statements_ordered_by_date(self, sample_statement, second_statement):
        save_statement(sample_statement)
        save_statement(second_statement)
        result = get_all_statements()

        assert len(result) == 2
        # second_statement has cut_off_date 2025-03-20, first has 2025-03-15
        assert result[0].card_number_masked == "XXXX XXXX XXXX 3251"
        assert result[1].card_number_masked == "XXXX XXXX XXXX 1075"

    def test_does_not_include_transactions(self, sample_statement):
        save_statement(sample_statement)
        result = get_all_statements()

        assert not hasattr(result[0], "transactions")
