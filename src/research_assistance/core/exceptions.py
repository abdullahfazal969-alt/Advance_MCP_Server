class ResearchAssistantError(Exception):
    """Base exception for Research Assistant server errors."""

    pass


class AccessDeniedError(ResearchAssistantError):
    """Raised when a user attempts to access a forbidden path."""

    pass


class DocumentNotFoundError(ResearchAssistantError):
    """Raised when a requested document is not found within allowed paths."""

    pass


# Add other specific exceptions as needed later
