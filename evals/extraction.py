from langsmith import Client

from agents.extraction import extract_structured_data
from evals.dataset import DATASET_NAME


def credit_card_statements_target(inputs):
    return extract_structured_data(pdf_content=inputs["pdf_text"]).model_dump(mode="json")


def credit_card_statements_evaluator(outputs: dict) -> bool:
    txs = outputs["transactions"]
    summary = outputs["summary"]
    total_gtq_transactions = sum(
        float(tx["amount"]) for tx in txs if tx["currency"] == "GTQ" and tx["transaction_type"] in ["purchase", "fee"]
    )
    return abs(total_gtq_transactions - float(summary["purchases_gtq"])) < 0.01


if __name__ == "__main__":
    client = Client()
    client.evaluate(
        credit_card_statements_target,
        data=DATASET_NAME,
        evaluators=[credit_card_statements_evaluator],
        experiment_prefix="extraction-flash-prompt-update-repetitions",
        max_concurrency=2,
        num_repetitions=3,
    )
