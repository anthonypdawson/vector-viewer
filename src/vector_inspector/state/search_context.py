"""Search context dataclass for storing query metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SearchContext:
    """Metadata about a search query.

    Holds the query text, optional embedding vector, the model and provider
    used to produce the embedding, and the time the search was issued.
    """

    query_text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    query_embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_provider: str | None = None
