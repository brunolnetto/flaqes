"""Introspection module for extracting schema information from databases."""

from flaqes.introspection.base import Introspector, IntrospectorProtocol
from flaqes.introspection.ddl_parser import (
    DDLParser,
    ParseError,
    ParseResult,
    parse_ddl,
    parse_ddl_file,
)
from flaqes.introspection.registry import (
    get_introspector,
    get_introspector_from_dsn,
    register_introspector,
)

__all__ = [
    "Introspector",
    "IntrospectorProtocol",
    "get_introspector",
    "get_introspector_from_dsn",
    "register_introspector",
    # DDL Parser
    "DDLParser",
    "ParseError",
    "ParseResult",
    "parse_ddl",
    "parse_ddl_file",
]
