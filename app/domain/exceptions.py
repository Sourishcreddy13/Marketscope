class MarketScopeException(Exception):
    """Base application exception."""


class InsufficientFundsException(MarketScopeException):
    pass


class InvalidOrderStateException(MarketScopeException):
    pass


class WatchlistUpdateException(MarketScopeException):
    pass


class DomainValidationException(MarketScopeException):
    pass


class InvalidInputException(DomainValidationException):
    """Input that is structurally acceptable to the schema but semantically invalid (e.g. blank after trimming)."""


class AccountSuspendedException(DomainValidationException):
    """Correct credentials, but the account is suspended."""


class IdempotencyConflictException(MarketScopeException):
    """An idempotency key was reused with a different request payload."""
