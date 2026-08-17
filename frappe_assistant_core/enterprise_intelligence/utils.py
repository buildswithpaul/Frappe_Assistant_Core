"""
Enterprise Intelligence Platform Utilities

Helper functions and utilities for the EIP system.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import frappe

from .constants import ConfidenceLevel, CONFIDENCE_THRESHOLDS, AlertSeverity


# ============================================================================
# Confidence Scoring
# ============================================================================


def get_confidence_level(score: float) -> ConfidenceLevel:
    """
    Convert confidence score (0-100) to confidence level.

    Args:
        score: Confidence score from 0 to 100

    Returns:
        ConfidenceLevel enum value
    """
    for level, (min_val, max_val) in CONFIDENCE_THRESHOLDS.items():
        if min_val <= score <= max_val:
            return level
    return ConfidenceLevel.VERY_LOW


def calculate_confidence(factors: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    """
    Calculate weighted confidence score from multiple factors.

    Args:
        factors: Dictionary of factor_name: score (0-100)
        weights: Dictionary of factor_name: weight (0-1). Auto-normalized if not provided.

    Returns:
        Weighted confidence score (0-100)
    """
    if not factors:
        return 0.0

    # Use equal weights if not provided
    if weights is None:
        weights = {key: 1.0 / len(factors) for key in factors.keys()}
    else:
        # Normalize weights
        total_weight = sum(weights.values())
        weights = {key: val / total_weight for key, val in weights.items()}

    # Calculate weighted score
    confidence = 0.0
    for factor_name, score in factors.items():
        weight = weights.get(factor_name, 0.0)
        confidence += score * weight

    return min(100.0, max(0.0, confidence))


# ============================================================================
# Data Validation
# ============================================================================


def validate_date_range(start_date: str, end_date: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date range.

    Args:
        start_date: Start date as string (YYYY-MM-DD)
        end_date: End date as string (YYYY-MM-DD)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        if start > end:
            return False, "Start date must be before end date"

        if (end - start).days > 3650:  # More than 10 years
            return False, "Date range cannot exceed 10 years"

        return True, None
    except ValueError as e:
        return False, f"Invalid date format: {str(e)}"


def normalize_data(data: List[Dict[str, Any]], exclude_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Normalize data by removing None values and standardizing format.

    Args:
        data: List of dictionaries to normalize
        exclude_fields: Fields to exclude from normalization

    Returns:
        Normalized data
    """
    if exclude_fields is None:
        exclude_fields = []

    normalized = []
    for item in data:
        normalized_item = {}
        for key, value in item.items():
            if key not in exclude_fields and value is not None:
                if isinstance(value, str):
                    normalized_item[key] = value.strip()
                else:
                    normalized_item[key] = value
        if normalized_item:
            normalized.append(normalized_item)

    return normalized


# ============================================================================
# Formatting
# ============================================================================


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format amount as currency string.

    Args:
        amount: Numeric amount
        currency: Currency code (default: USD)

    Returns:
        Formatted currency string
    """
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "EUR":
        return f"€{amount:,.2f}"
    elif currency == "GBP":
        return f"£{amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format value as percentage string.

    Args:
        value: Numeric value (0-100)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string
    """
    return f"{value:.{decimals}f}%"


def format_large_number(value: int) -> str:
    """
    Format large number with K, M, B suffixes.

    Args:
        value: Numeric value

    Returns:
        Formatted string
    """
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


# ============================================================================
# Alerting
# ============================================================================


def should_alert(current_value: float, threshold: float, alert_on: str = "above") -> bool:
    """
    Determine if alert should be triggered.

    Args:
        current_value: Current metric value
        threshold: Threshold value
        alert_on: "above", "below", or "change"

    Returns:
        True if alert should be triggered
    """
    if alert_on == "above":
        return current_value > threshold
    elif alert_on == "below":
        return current_value < threshold
    elif alert_on == "change":
        return abs(current_value - threshold) > (threshold * 0.1)  # 10% change
    return False


def get_alert_severity(score: float) -> AlertSeverity:
    """
    Determine alert severity based on score.

    Args:
        score: Severity score (0-100)

    Returns:
        AlertSeverity enum value
    """
    if score >= 90:
        return AlertSeverity.CRITICAL
    elif score >= 70:
        return AlertSeverity.HIGH
    elif score >= 50:
        return AlertSeverity.MEDIUM
    elif score >= 30:
        return AlertSeverity.LOW
    return AlertSeverity.INFO


# ============================================================================
# Time Operations
# ============================================================================


def get_date_range(period: str = "last_month") -> Tuple[datetime, datetime]:
    """
    Get date range for common periods.

    Args:
        period: "last_month", "last_quarter", "last_year", "ytd"

    Returns:
        Tuple of (start_date, end_date)
    """
    today = datetime.now().date()
    end_date = datetime.combine(today, datetime.min.time())

    if period == "last_month":
        start_date = end_date - timedelta(days=30)
    elif period == "last_quarter":
        start_date = end_date - timedelta(days=90)
    elif period == "last_year":
        start_date = end_date - timedelta(days=365)
    elif period == "ytd":
        start_date = datetime.combine(
            datetime(today.year, 1, 1).date(), datetime.min.time()
        )
    else:
        start_date = end_date - timedelta(days=30)

    return start_date, end_date


def format_time_delta(seconds: float) -> str:
    """
    Format time delta in human-readable format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{int(minutes)}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{int(hours)}h"
    else:
        days = seconds / 86400
        return f"{int(days)}d"
