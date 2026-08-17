"""
Enterprise Intelligence Platform Constants

Defines all enumerations, constants, and configurations for the EIP system.
"""

from enum import Enum
from typing import Dict, List

# ============================================================================
# Decision Intent Types
# ============================================================================


class DecisionIntentType(str, Enum):
    """Types of business decisions the user is considering"""

    STRATEGIC_EXPANSION = "strategic_expansion"
    COST_OPTIMIZATION = "cost_optimization"
    RISK_MITIGATION = "risk_mitigation"
    MARKET_ENTRY = "market_entry"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    DIVESTMENT = "divestment"
    OPERATIONAL_IMPROVEMENT = "operational_improvement"
    GENERAL_ANALYSIS = "general_analysis"


# ============================================================================
# Business Areas
# ============================================================================


class BusinessArea(str, Enum):
    """Business functional areas"""

    SALES = "sales"
    INVENTORY = "inventory"
    FINANCE = "finance"
    OPERATIONS = "operations"
    PROCUREMENT = "procurement"
    HR = "hr"
    CRM = "crm"
    PROJECTS = "projects"
    MANUFACTURING = "manufacturing"
    GENERAL = "general"


# ============================================================================
# Alert & Severity Levels
# ============================================================================


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts"""

    ANOMALY = "anomaly"
    THRESHOLD = "threshold"
    TREND_BREAK = "trend_break"
    CONCENTRATION = "concentration"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    OPPORTUNITY = "opportunity"
    RISK = "risk"


# ============================================================================
# Confidence Levels
# ============================================================================


class ConfidenceLevel(str, Enum):
    """Confidence level classifications"""

    VERY_HIGH = "very_high"  # 95-100%
    HIGH = "high"  # 80-95%
    MEDIUM = "medium"  # 60-80%
    LOW = "low"  # 40-60%
    VERY_LOW = "very_low"  # <40%


# ============================================================================
# Scan Types
# ============================================================================


class ScanType(str, Enum):
    """Types of enterprise scans"""

    CUSTOMERS = "customers"
    PRODUCTS = "products"
    SALES = "sales"
    GEOGRAPHY = "geography"
    INVENTORY = "inventory"
    MARGINS = "margins"
    SUPPLIERS = "suppliers"
    OPERATIONS = "operations"
    FINANCE = "finance"
    HR = "hr"


# ============================================================================
# Scenario Risk Levels
# ============================================================================


class RiskLevel(str, Enum):
    """Risk level assessment"""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"
    NONE = "none"


# ============================================================================
# Decision Status
# ============================================================================


class DecisionStatus(str, Enum):
    """Decision status through lifecycle"""

    INITIATED = "initiated"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    RECOMMENDING = "recommending"
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTING = "implementing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# ============================================================================
# Scan Configuration
# ============================================================================

# Default scans for each decision intent
DEFAULT_SCANS_BY_INTENT: Dict[DecisionIntentType, List[ScanType]] = {
    DecisionIntentType.STRATEGIC_EXPANSION: [
        ScanType.CUSTOMERS,
        ScanType.PRODUCTS,
        ScanType.SALES,
        ScanType.GEOGRAPHY,
        ScanType.INVENTORY,
        ScanType.MARGINS,
        ScanType.SUPPLIERS,
    ],
    DecisionIntentType.COST_OPTIMIZATION: [
        ScanType.OPERATIONS,
        ScanType.SUPPLIERS,
        ScanType.PRODUCTS,
        ScanType.INVENTORY,
        ScanType.FINANCE,
    ],
    DecisionIntentType.RISK_MITIGATION: [
        ScanType.CUSTOMERS,
        ScanType.FINANCE,
        ScanType.SALES,
        ScanType.INVENTORY,
    ],
    DecisionIntentType.MARKET_ENTRY: [
        ScanType.CUSTOMERS,
        ScanType.SALES,
        ScanType.GEOGRAPHY,
        ScanType.PRODUCTS,
        ScanType.MARGINS,
    ],
    DecisionIntentType.GENERAL_ANALYSIS: [
        ScanType.SALES,
        ScanType.CUSTOMERS,
        ScanType.PRODUCTS,
        ScanType.FINANCE,
    ],
}

# ============================================================================
# Confidence Thresholds
# ============================================================================

# Confidence score ranges (0-100)
CONFIDENCE_THRESHOLDS = {
    ConfidenceLevel.VERY_HIGH: (95, 100),
    ConfidenceLevel.HIGH: (80, 95),
    ConfidenceLevel.MEDIUM: (60, 80),
    ConfidenceLevel.LOW: (40, 60),
    ConfidenceLevel.VERY_LOW: (0, 40),
}

# Minimum confidence required for recommendation
MIN_CONFIDENCE_FOR_RECOMMENDATION = 60

# ============================================================================
# Performance & Timeouts
# ============================================================================

# Scan execution timeouts (seconds)
SCAN_TIMEOUTS = {
    ScanType.CUSTOMERS: 30,
    ScanType.PRODUCTS: 25,
    ScanType.SALES: 35,
    ScanType.GEOGRAPHY: 20,
    ScanType.INVENTORY: 25,
    ScanType.MARGINS: 30,
    ScanType.SUPPLIERS: 20,
    ScanType.OPERATIONS: 40,
    ScanType.FINANCE: 35,
    ScanType.HR: 25,
}

# Cache duration (seconds)
CACHE_DURATION = {
    "customer_segment": 3600,  # 1 hour
    "product_analysis": 3600,
    "sales_trend": 1800,  # 30 minutes
    "market_data": 86400,  # 1 day
    "competitor_data": 86400,
    "industry_data": 604800,  # 7 days
}

# ============================================================================
# Anomaly Detection Thresholds
# ============================================================================

ANOMALY_THRESHOLDS = {
    "margin_change_percent": 5.0,  # Alert if margin changes >5%
    "revenue_growth_percent": 10.0,  # Alert if growth >10%
    "customer_concentration": 40.0,  # Alert if top 3 customers > 40%
    "inventory_turnover": 20.0,  # Alert if turnover > 20%
    "receivables_days": 60,  # Alert if receivables > 60 days
}

# ============================================================================
# Default Configurations
# ============================================================================

DEFAULT_CONFIG = {
    "enable_continuous_monitoring": True,
    "monitoring_frequency_minutes": 60,
    "enable_external_intelligence": True,
    "enable_anomaly_detection": True,
    "enable_scenario_analysis": True,
    "min_confidence_threshold": MIN_CONFIDENCE_FOR_RECOMMENDATION,
    "max_scan_results": 1000,
    "cache_enabled": True,
}
