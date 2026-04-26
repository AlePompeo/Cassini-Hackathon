"""Custom exceptions for AquaGuard processing pipeline."""


class AquaGuardError(Exception):
    """Base exception for all AquaGuard errors."""


class ProcessingError(AquaGuardError):
    """Raised when satellite image processing fails."""


class DataSourceError(AquaGuardError):
    """Raised when data cannot be fetched from Copernicus or other sources."""


class ModelError(AquaGuardError):
    """Raised when the trajectory or classification model encounters an error."""
