"""Exceptions shared across application boundaries."""


class InvalidPositionError(ValueError):
    """A collection of positions violates a domain invariant."""


class RepositoryError(RuntimeError):
    """A repository could not complete a data operation."""


class ReportFetchError(RuntimeError):
    """An external report source could not provide reports."""


class PositionPublishError(RuntimeError):
    """A position could not be accepted by its publishing destination."""
