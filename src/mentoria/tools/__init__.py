"""Tools e integracoes externas do MentorIA."""

from mentoria.tools.dictionary import (
    DictionaryClient,
    DictionaryResult,
    InvalidWordError,
    dictionary_lookup,
    lookup_word,
)

__all__ = [
    "DictionaryClient",
    "DictionaryResult",
    "InvalidWordError",
    "dictionary_lookup",
    "lookup_word",
]
