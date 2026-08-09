"""User-oriented conversion errors."""


class ConversionError(Exception):
    """An expected error that can be presented without a traceback."""


class PasswordRequiredError(ConversionError):
    """The supplied PDF requires a valid user password."""


class ValidationError(ConversionError):
    """An EPUB package did not pass internal validation."""


class ConversionCancelled(ConversionError):
    """A user requested cancellation."""
