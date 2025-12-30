"""Introspection module for extracting schema information from databases."""

from flakes.introspection.base import Introspector, IntrospectorProtocol
from flakes.introspection.registry import (
    get_introspector,
    register_introspector,
)

__all__ = [
    "Introspector",
    "IntrospectorProtocol",
    "get_introspector",
    "register_introspector",
]
