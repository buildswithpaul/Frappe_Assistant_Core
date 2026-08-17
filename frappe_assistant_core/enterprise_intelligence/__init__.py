"""
Enterprise Intelligence Platform Module

Core module for intelligent business decision-making capabilities.
Extends Frappe Assistant Core with advanced analytics, risk detection, and recommendations.
"""

__version__ = "1.0.0"
__author__ = "Enterprise Intelligence Platform Team"

from .constants import *  # noqa: F401, F403
from .exceptions import *  # noqa: F401, F403
from .decorators import *  # noqa: F401, F403

__all__ = [
    "DecisionIntentType",
    "AlertSeverity",
    "ConfidenceLevel",
    "ScanType",
    "BusinessArea",
    "AlertType",
    "RiskLevel",
    "DecisionStatus",
    "cache_result",
    "log_performance",
    "track_metrics",
    "handle_errors",
    "retry",
    "validate_input",
    "IntelligenceError",
    "ScanError",
    "AnalysisError",
    "RecommendationError",
]
