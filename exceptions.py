"""
Custom domain exception hierarchy for the Automatic Block Planning System (ABPS).
"""

class RailwaySchedulerError(Exception):
    """Base exception for all railway scheduler domain errors."""
    pass


class SecurityValidationError(RailwaySchedulerError):
    """Raised when request authentication, authorization, or input validation fails."""
    pass


class ResourceContentionError(RailwaySchedulerError):
    """Raised when machine fleet or track section resources are mutually contested."""
    pass


class SafetyViolationError(RailwaySchedulerError):
    """Raised when railway interlocking or 25kV OHE safety rules are infringed."""
    pass


class DataIntegrityError(RailwaySchedulerError):
    """Raised when database records or timetable intervals fail integrity checks."""
    pass
