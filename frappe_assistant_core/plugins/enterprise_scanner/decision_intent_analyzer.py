"""
Decision Intent Analyzer Tool

Analyzes user input to determine business decision intent and required scans.
"""

from typing import Dict, List, Any, Optional
import frappe
from ..enhanced_base_tool import EnhancedBaseTool
from ..constants import DecisionIntentType, ScanType, BusinessArea, DEFAULT_SCANS_BY_INTENT
from ..decorators import cache_result, log_performance
from ..exceptions import IntentAnalysisError


class DecisionIntentAnalyzerTool(EnhancedBaseTool):
    """
    Analyzes business decision intent from user input.
    
    Determines:
    - Type of business decision being considered
    - Relevant business areas
    - Required scans to perform
    - Confidence in analysis
    """

    name = "decision_intent_analyzer"
    description = "Analyzes business decision intent and determines required scans"

    def _execute_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute intent analysis."""
        user_input = arguments.get("user_input", "")
        
        if not user_input or not user_input.strip():
            raise IntentAnalysisError("User input is required")

        # Analyze intent
        intent_type, confidence = self._analyze_intent(user_input)
        
        # Determine required scans
        required_scans = self._get_required_scans(intent_type)
        
        # Identify business areas
        business_areas = self._identify_business_areas(user_input)
        
        # Extract key metrics
        key_metrics = self._extract_key_metrics(user_input)

        return {
            "success": True,
            "intent": intent_type.value if intent_type else None,
            "intent_confidence": confidence,
            "required_scans": [scan.value for scan in required_scans],
            "business_areas": [area.value for area in business_areas],
            "key_metrics": key_metrics,
            "analysis_summary": self._generate_summary(
                intent_type, required_scans, business_areas
            ),
        }

    @cache_result(duration=3600, key_prefix="intent_analysis")
    @log_performance(threshold_ms=1000)
    def _analyze_intent(self, user_input: str) -> tuple:
        """Analyze and classify decision intent from user input."""
        user_input_lower = user_input.lower()

        # Intent keywords mapping
        intent_patterns = {
            DecisionIntentType.STRATEGIC_EXPANSION: [
                "expand", "growth", "market", "new market", "scale", "grow",
                "increase revenue", "enter market", "expansion"
            ],
            DecisionIntentType.COST_OPTIMIZATION: [
                "cost", "reduce cost", "save", "efficiency", "optimize",
                "cut cost", "reduce expenses", "cheaper", "discount"
            ],
            DecisionIntentType.RISK_MITIGATION: [
                "risk", "mitigate", "safe", "security", "protect", "reduce risk",
                "compliance", "avoid loss", "insurance"
            ],
            DecisionIntentType.MARKET_ENTRY: [
                "market entry", "enter", "penetrate", "new region",
                "new customer", "customer acquisition", "market share"
            ],
            DecisionIntentType.PRODUCT_LAUNCH: [
                "product", "launch", "new product", "release", "introduce",
                "new service", "offering"
            ],
            DecisionIntentType.PARTNERSHIP: [
                "partner", "collaboration", "alliance", "joint venture",
                "merge", "cooperation"
            ],
            DecisionIntentType.ACQUISITION: [
                "acquire", "buyout", "takeover", "purchase", "buy",
                "acquisition", "merger"
            ],
        }

        # Score each intent
        intent_scores = {}
        for intent, keywords in intent_patterns.items():
            score = sum(
                1 for keyword in keywords if keyword in user_input_lower
            )
            intent_scores[intent] = score

        # Get top intent
        if max(intent_scores.values()) > 0:
            top_intent = max(intent_scores, key=intent_scores.get)
            max_score = intent_scores[top_intent]
            total_score = max(sum(intent_scores.values()), 1)
            confidence = min(100.0, (max_score / total_score) * 100)
            return top_intent, confidence
        else:
            return DecisionIntentType.GENERAL_ANALYSIS, 40.0

    def _get_required_scans(self, intent_type: Optional[DecisionIntentType]) -> List[ScanType]:
        """Get required scans for the identified intent."""
        if not intent_type:
            return [ScanType.SALES, ScanType.CUSTOMERS, ScanType.PRODUCTS]

        return DEFAULT_SCANS_BY_INTENT.get(
            intent_type,
            [ScanType.SALES, ScanType.CUSTOMERS, ScanType.PRODUCTS]
        )

    def _identify_business_areas(self, user_input: str) -> List[BusinessArea]:
        """Identify affected business areas from user input."""
        user_input_lower = user_input.lower()

        areas_keywords = {
            BusinessArea.SALES: ["sales", "revenue", "customer", "deal", "order"],
            BusinessArea.INVENTORY: ["inventory", "stock", "warehouse", "supply"],
            BusinessArea.FINANCE: ["finance", "budget", "cost", "profit", "margin"],
            BusinessArea.OPERATIONS: ["operation", "process", "efficiency", "capacity"],
            BusinessArea.PROCUREMENT: ["supplier", "purchase", "procurement", "sourcing"],
            BusinessArea.HR: ["employee", "staff", "team", "hr", "people"],
            BusinessArea.CRM: ["customer", "crm", "relationship", "account"],
            BusinessArea.PROJECTS: ["project", "timeline", "delivery", "scope"],
        }

        identified_areas = []
        for area, keywords in areas_keywords.items():
            if any(keyword in user_input_lower for keyword in keywords):
                identified_areas.append(area)

        return identified_areas if identified_areas else [BusinessArea.GENERAL]

    def _extract_key_metrics(self, user_input: str) -> Dict[str, Any]:
        """Extract key metrics mentioned in user input."""
        import re

        metrics = {}

        # Look for percentages
        percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', user_input)
        if percentages:
            metrics["percentages_mentioned"] = [float(p) for p in percentages]

        # Look for currency amounts
        currency_pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
        amounts = re.findall(currency_pattern, user_input)
        if amounts:
            metrics["currency_amounts"] = amounts

        # Look for time periods
        time_keywords = {
            "short_term": ["week", "month", "quarter"],
            "medium_term": ["year", "annual"],
            "long_term": ["years", "decade"],
        }
        
        for period, keywords in time_keywords.items():
            if any(kw in user_input.lower() for kw in keywords):
                metrics[f"timeline"] = period
                break

        return metrics

    def _generate_summary(
        self,
        intent_type: Optional[DecisionIntentType],
        scans: List[ScanType],
        areas: List[BusinessArea]
    ) -> str:
        """Generate human-readable analysis summary."""
        intent_text = intent_type.value.replace("_", " ").title() if intent_type else "General Analysis"
        
        scans_text = ", ".join([s.value.replace("_", " ").title() for s in scans[:3]])
        areas_text = ", ".join([a.value.title() for a in areas[:3]])

        summary = (
            f"Decision Intent: {intent_text}. "
            f"Required scans: {scans_text}. "
            f"Affected areas: {areas_text}."
        )

        return summary
