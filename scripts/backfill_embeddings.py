"""Backfill embeddings for transactions that don't have one yet.

Run with: uv run python -m scripts.backfill_embeddings
"""

import logging

from agents.embeddings import embed_texts
from db.cruds import get_transactions_missing_embeddings, set_transaction_embeddings

BATCH_SIZE = 100

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    pending = get_transactions_missing_embeddings()
    if not pending:
        log.info("All transactions already have embeddings.")
        return

    log.info("Backfilling %d transactions...", len(pending))
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        ids = [row[0] for row in batch]
        descriptions = [row[1] for row in batch]
        vectors = embed_texts(descriptions)
        updated = set_transaction_embeddings(dict(zip(ids, vectors, strict=True)))
        log.info("Embedded batch %d (%d rows)", i // BATCH_SIZE + 1, updated)

    log.info("Done.")


if __name__ == "__main__":
    main()
