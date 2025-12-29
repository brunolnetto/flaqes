"""
Registry for database introspectors.

This module provides a registry pattern for discovering and instantiating
database-specific introspectors. New engines are registered here.
"""

from typing import Callable

from flakes.introspection.base import Introspector

# Type alias for introspector factory functions
IntrospectorFactory = Callable[[str], Introspector]

# Registry mapping engine names to factory functions
_registry: dict[str, IntrospectorFactory] = {}


def register_introspector(engine: str) -> Callable[[type[Introspector]], type[Introspector]]:
    """
    Decorator to register an introspector class for an engine.
    
    Usage:
        @register_introspector("postgresql")
        class PostgreSQLIntrospector(Introspector):
            ...
    
    Args:
        engine: Engine identifier (e.g., 'postgresql', 'mysql').
    
    Returns:
        Decorator that registers the class.
    """
    def decorator(cls: type[Introspector]) -> type[Introspector]:
        _registry[engine] = cls
        return cls
    return decorator


def _ensure_engine_loaded(engine: str) -> None:
    """
    Lazily load an engine's introspector module if not already registered.
    
    This allows engines to be optional dependencies that are only imported
    when actually needed.
    """
    if engine in _registry:
        return
    
    # Attempt lazy import for known engines
    if engine == "postgresql":
        try:
            import flakes.introspection.postgresql  # noqa: F401
        except ImportError as e:
            raise ImportError(
                f"PostgreSQL support requires asyncpg. "
                f"Install with: pip install flakes[postgresql]\n"
                f"Original error: {e}"
            ) from e
    elif engine == "mysql":
        raise NotImplementedError(
            "MySQL support is not yet implemented. "
            "Contributions welcome!"
        )
    elif engine == "sqlite":
        raise NotImplementedError(
            "SQLite support is not yet implemented. "
            "Contributions welcome!"
        )


def get_introspector(engine: str, dsn: str) -> Introspector:
    """
    Get an introspector instance for the specified engine.
    
    Args:
        engine: Engine identifier (e.g., 'postgresql', 'mysql').
        dsn: Database connection string.
    
    Returns:
        Introspector instance for the engine.
    
    Raises:
        ValueError: If engine is not supported.
        ImportError: If engine's dependencies are not installed.
    
    Example:
        >>> introspector = get_introspector("postgresql", "postgresql://localhost/mydb")
        >>> async with introspector:
        ...     result = await introspector.introspect()
    """
    # Try to lazily load the engine
    _ensure_engine_loaded(engine)
    
    if engine not in _registry:
        supported = ", ".join(sorted(_registry.keys())) or "none"
        raise ValueError(
            f"Unsupported database engine: '{engine}'. "
            f"Supported engines: {supported}"
        )
    
    factory = _registry[engine]
    return factory(dsn)


def get_introspector_from_dsn(dsn: str) -> Introspector:
    """
    Get an introspector by inferring the engine from the DSN.
    
    Supports common DSN formats:
    - postgresql://... or postgres://...
    - mysql://...
    - sqlite:///...
    
    Args:
        dsn: Database connection string.
    
    Returns:
        Introspector instance for the inferred engine.
    
    Raises:
        ValueError: If engine cannot be inferred or is not supported.
        ImportError: If engine's dependencies are not installed.
    """
    dsn_lower = dsn.lower()
    
    if dsn_lower.startswith(("postgresql://", "postgres://")):
        engine = "postgresql"
    elif dsn_lower.startswith("mysql://"):
        engine = "mysql"
    elif dsn_lower.startswith("sqlite://"):
        engine = "sqlite"
    else:
        raise ValueError(
            f"Cannot infer database engine from DSN: '{dsn[:20]}...'. "
            "Please use get_introspector() with an explicit engine parameter."
        )
    
    return get_introspector(engine, dsn)


def list_supported_engines() -> list[str]:
    """
    List all registered/supported database engines.
    
    Returns:
        Sorted list of engine identifiers.
    """
    return sorted(_registry.keys())


def is_engine_supported(engine: str) -> bool:
    """
    Check if an engine is supported.
    
    Args:
        engine: Engine identifier.
    
    Returns:
        True if engine has a registered introspector.
    """
    return engine in _registry
