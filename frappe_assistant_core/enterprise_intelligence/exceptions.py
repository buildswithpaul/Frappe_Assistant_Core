"""
Enterprise Intelligence Platform Exceptions

Custom exception classes for the EIP system.
"""


class IntelligenceError(Exception):
    """Base exception for Enterprise Intelligence Platform"""

    pass


class ScanError(IntelligenceError):
    """Exception raised during enterprise scanning"""

    pass


class DataSourceError(IntelligenceError):
    """Exception raised when accessing data sources"""

    pass


class AnalysisError(IntelligenceError):
    """Exception raised during analysis operations"""

    pass


class RecommendationError(IntelligenceError):
    """Exception raised during recommendation generation"""

    pass


class ConfigurationError(IntelligenceError):
    """Exception raised for configuration issues"""

    pass


class IntentAnalysisError(IntelligenceError):
    """Exception raised during intent analysis"""

    pass


class AnomalyDetectionError(IntelligenceError):
    """Exception raised during anomaly detection"""

    pass


class ExternalIntelligenceError(IntelligenceError):
    """Exception raised when fetching external intelligence"""

    pass


class ScenarioGenerationError(IntelligenceError):
    """Exception raised during scenario generation"""

    pass


class AnomalyDetectionTimeout(AnomalyDetectionError):
    """Timeout exception for anomaly detection"""

    pass


class DataValidationError(IntelligenceError):
    """Exception raised when data validation fails"""

    pass


class PermissionError(IntelligenceError):
    """Exception raised for permission issues"""

    pass


class RateLimitError(IntelligenceError):
    """Exception raised when API rate limit exceeded"""

    pass
