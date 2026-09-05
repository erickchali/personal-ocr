import os

from langsmith import Client

from config import settings  # noqa

DATASET_NAME = "credit_card_statements_dataset"


def create_credit_card_statemants_dataset():
    client = Client()
    try:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="contains banco industrial, bac, and promerica statements data",
        )
    except Exception:
        dataset = client.read_dataset(dataset_name=DATASET_NAME)

    if dataset:
        existing_examples = list(client.list_examples(dataset_id=dataset.id))
        if existing_examples:
            print(f"Force recreate: Deleting {len(existing_examples)} existing examples...")
            for ex in existing_examples:
                client.delete_example(ex.id)
            print("Existing examples deleted.")

    with open(f"{os.getcwd()}/evals/fixtures/01-mc-black.txt", encoding="utf-8") as statement_1:
        statement_1_text = statement_1.read()
    with open(f"{os.getcwd()}/evals/fixtures/02-bac-visa.txt", encoding="utf-8") as statement_2:
        statement_2_text = statement_2.read()
    with open(f"{os.getcwd()}/evals/fixtures/03-promerica.txt", encoding="utf-8") as statement_3:
        statement_3_text = statement_3.read()
    with open(f"{os.getcwd()}/evals/fixtures/04-mc-black-subtotal.txt", encoding="utf-8") as statement_4:
        statement_4_text = statement_4.read()

    examples = [
        {
            "inputs": {
                "pdf_text": str(statement_1_text),
                "source": "01-mc-black.txt",
            }
        },
        {
            "inputs": {
                "pdf_text": str(statement_2_text),
                "source": "02-bac-visa.txt",
            }
        },
        {
            "inputs": {
                "pdf_text": str(statement_3_text),
                "source": "03-promerica.txt",
            }
        },
        {
            "inputs": {
                "pdf_text": str(statement_4_text),
                "source": "04-mc-black-subtotal.txt",
            }
        },
    ]
    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"created {len(examples)} examples on dataset")


if __name__ == "__main__":
    create_credit_card_statemants_dataset()
