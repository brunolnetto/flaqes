"""Introspection module for extracting schema information from databases."""

from flaqes.introspection.base import Introspector, IntrospectorProtocol
from flaqes.introspection.registry import (
    get_introspector,
    register_introspector,
)

__all__ = [
    "Introspector",
    "IntrospectorProtocol",
    "get_introspector",
    "register_introspector",
]
