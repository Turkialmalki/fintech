"""Vector column that works with pgvector when available and falls back to float8[].

pgvector defines an assignment cast from double precision[] to vector, so binding a Python
list works for both column kinds. Results from a pgvector column arrive as text "[...]".
"""
from __future__ import annotations

import json

from sqlalchemy import Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator


class EmbeddingVector(TypeDecorator):
    impl = ARRAY(Float)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return list(value)


from sqlalchemy.types import UserDefinedType  # noqa: E402


class PgVector(UserDefinedType):
    """Used only to CAST query parameters to pgvector's `vector` type."""

    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector"
