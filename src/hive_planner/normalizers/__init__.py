from __future__ import annotations

from hive_planner.models import NormalizeResult


class NormalizationError(Exception):
    """Base error for source normalization failures."""


class MissingDependencyError(NormalizationError):
    """Optional format dependency not installed."""


class EmptySourceError(NormalizationError):
    """Source file has no extractable text."""
