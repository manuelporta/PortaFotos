
class UnknownError(Exception):
    """Raised when an unexpected error occurs."""

    def __init__(self, message: str = "An unknown error has occurred."):
        super().__init__(message)
        self.message = message
