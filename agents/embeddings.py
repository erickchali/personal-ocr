"""Embedding model factory.

Uses OpenAI's text-embedding-3-small (1536 dims) to vectorize transaction
descriptions and user queries so the LLM can do semantic search.
"""

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

EMBEDDING_MODEL = "text-embedding-3-small"


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    return get_embeddings().embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embeddings().embed_documents(texts)
