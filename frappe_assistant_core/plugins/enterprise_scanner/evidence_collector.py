"""
Evidence Collector

Collects and consolidates evidence from all scans into a unified intelligence pack.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import frappe
from ..enhanced_base_tool import EnhancedBaseTool
from ..constants import AlertSeverity, ConfidenceLevel
from ..decorators import log_performance, cache_result
from ..exceptions import AnalysisError


class EvidenceCollector(EnhancedBaseTool):
    """
    Evidence Collector
    
    Consolidates evidence from all scans:
    - Aggregates scan results
    - Identifies patterns and correlations
    - Creates evidence packs
    - Scores evidence quality and relevance
    - Manages evidence lifecycle
    """

    name = "evidence_collector"
    description = "Collects and consolidates scan evidence into intelligence packs"

    def _execute_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute evidence collection."""
        scan_results = arguments.get("scan_results", [])
        intent = arguments.get("intent")
        date_range = arguments.get("date_range", "last_month")
        
        if not scan_results:
            raise AnalysisError("No scan results provided")

        try:
            # Consolidate evidence
            evidence_pack = self._consolidate_evidence(scan_results, intent)
            
            # Score evidence
            evidence_pack = self._score_evidence(evidence_pack)
            
            # Identify patterns
            patterns = self._identify_patterns(evidence_pack)
            evidence_pack["patterns"] = patterns
            
            # Generate evidence summary
            summary = self._generate_evidence_summary(evidence_pack)
            evidence_pack["summary"] = summary
            
            return {
                "success": True,
                "evidence_pack_id": self._generate_pack_id(),
                "evidence_pack": evidence_pack,
                "confidence": 90.0,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise AnalysisError(f"Evidence collection failed: {str(e)}")

    def _consolidate_evidence(
        self, 
        scan_results: List[Dict[str, Any]], 
        intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Consolidate evidence from multiple scan results."""
        consolidated = {
            "collection_time": datetime.now().isoformat(),
            "intent": intent,
            "scans": [],
            "evidence_items": [],
            "metrics_summary": {},
            "alerts": [],
            "opportunities": [],
        }

        for scan_result in scan_results:
            if not scan_result.get("success", False):
                continue

            scan_type = scan_result.get("scan_type", "unknown")
            confidence = scan_result.get("confidence", 0)

            # Add scan to pack
            scan_entry = {
                "type": scan_type,
                "confidence": confidence,
                "timestamp": scan_result.get("timestamp"),
                "summary": scan_result.get("summary", {}),
            }
            consolidated["scans"].append(scan_entry)

            # Extract evidence items
            evidence_items = self._extract_evidence_items(scan_result)
            consolidated["evidence_items"].extend(evidence_items)

            # Aggregate metrics
            if "summary" in scan_result:
                consolidated["metrics_summary"][scan_type] = scan_result["summary"]

        return consolidated

    def _extract_evidence_items(self, scan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual evidence items from scan result."""
        evidence_items = []
        scan_type = scan_result.get("scan_type", "unknown")

        # Extract specific evidence based on scan type
        if scan_type == "customers":
            concentration = scan_result.get("concentration_risk", 0)
            if concentration > 40:
                evidence_items.append({
                    "type": "concentration_risk",
                    "severity": AlertSeverity.HIGH.value if concentration > 60 else AlertSeverity.MEDIUM.value,
                    "metric": "customer_concentration",
                    "value": concentration,
                    "unit": "%",
                    "threshold": 40,
                    "description": f"Top 3 customers represent {concentration:.1f}% of revenue",
                })

        elif scan_type == "sales":
            growth = scan_result.get("monthly_growth", 0)
            trend = "positive" if growth > 0 else "negative"
            evidence_items.append({
                "type": "growth_trend",
                "severity": AlertSeverity.INFO.value,
                "metric": "monthly_growth",
                "value": growth,
                "unit": "%",
                "trend": trend,
                "description": f"Monthly sales growth: {growth:.1f}%",
            })

        elif scan_type == "products":
            concentration = scan_result.get("concentration", 0)
            if concentration > 50:
                evidence_items.append({
                    "type": "product_concentration",
                    "severity": AlertSeverity.MEDIUM.value,
                    "metric": "product_concentration",
                    "value": concentration,
                    "unit": "%",
                    "description": f"Top 10 products represent {concentration:.1f}% of revenue",
                })

        elif scan_type == "inventory":
            total_value = scan_result.get("total_inventory_value", 0)
            evidence_items.append({
                "type": "inventory_value",
                "severity": AlertSeverity.INFO.value,
                "metric": "inventory_value",
                "value": total_value,
                "unit": "currency",
                "description": f"Total inventory value: ${total_value:,.2f}",
            })

        return evidence_items

    def _score_evidence(self, evidence_pack: Dict[str, Any]) -> Dict[str, Any]:
        """Score evidence quality and relevance."""
        # Overall confidence
        confidences = [scan.get("confidence", 0) for scan in evidence_pack.get("scans", [])]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Completeness score
        completeness = len(evidence_pack.get("evidence_items", [])) / max(
            len(evidence_pack.get("scans", [])) * 3, 1
        ) * 100
        completeness = min(100, completeness)

        # Recency score (more recent = higher score)
        recency = 95  # Default high score for recent data

        # Consistency score
        consistency = self._score_consistency(evidence_pack.get("evidence_items", []))

        # Overall evidence quality
        evidence_quality = (
            overall_confidence * 0.4 +
            completeness * 0.25 +
            recency * 0.2 +
            consistency * 0.15
        )

        evidence_pack["scoring"] = {
            "overall_confidence": overall_confidence,
            "completeness": completeness,
            "recency": recency,
            "consistency": consistency,
            "evidence_quality": min(100, evidence_quality),
        }

        return evidence_pack

    def _score_consistency(self, evidence_items: List[Dict[str, Any]]) -> float:
        """Score consistency of evidence."""
        if not evidence_items:
            return 50.0

        # Check for conflicting signals
        positive_signals = sum(
            1 for item in evidence_items 
            if item.get("trend") == "positive" or item.get("severity") in [AlertSeverity.INFO.value]
        )
        
        negative_signals = sum(
            1 for item in evidence_items 
            if item.get("trend") == "negative" or item.get("severity") == AlertSeverity.HIGH.value
        )

        if positive_signals + negative_signals == 0:
            return 50.0

        # Higher score if signals are aligned
        max_signals = max(positive_signals, negative_signals)
        total_signals = positive_signals + negative_signals
        consistency = (max_signals / total_signals) * 100

        return consistency

    def _identify_patterns(self, evidence_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify patterns from consolidated evidence."""
        patterns = []
        evidence_items = evidence_pack.get("evidence_items", [])

        # Pattern 1: Concentration risk
        concentration_items = [
            item for item in evidence_items 
            if item.get("type") in ["concentration_risk", "product_concentration"]
        ]
        if concentration_items:
            avg_concentration = sum(
                item.get("value", 0) for item in concentration_items
            ) / len(concentration_items)
            patterns.append({
                "pattern": "concentration_dependency",
                "severity": AlertSeverity.HIGH.value if avg_concentration > 50 else AlertSeverity.MEDIUM.value,
                "description": "Business shows concentration risk across multiple dimensions",
                "average_concentration": avg_concentration,
                "affected_dimensions": len(concentration_items),
            })

        # Pattern 2: Growth trends
        growth_items = [
            item for item in evidence_items 
            if item.get("type") == "growth_trend"
        ]
        if growth_items:
            avg_growth = sum(
                item.get("value", 0) for item in growth_items
            ) / len(growth_items)
            patterns.append({
                "pattern": "growth_trajectory",
                "trend": "positive" if avg_growth > 0 else "negative",
                "average_growth": avg_growth,
                "description": f"Overall growth trend is {avg_growth:.1f}% monthly",
            })

        # Pattern 3: Risk indicators
        high_severity_items = [
            item for item in evidence_items 
            if item.get("severity") == AlertSeverity.HIGH.value
        ]
        if high_severity_items:
            patterns.append({
                "pattern": "high_risk_indicators",
                "severity": AlertSeverity.HIGH.value,
                "count": len(high_severity_items),
                "description": f"Identified {len(high_severity_items)} high-risk indicators",
                "indicators": [item.get("description") for item in high_severity_items],
            })

        return patterns

    def _generate_evidence_summary(self, evidence_pack: Dict[str, Any]) -> str:
        """Generate human-readable evidence summary."""
        scans_count = len(evidence_pack.get("scans", []))
        evidence_count = len(evidence_pack.get("evidence_items", []))
        patterns_count = len(evidence_pack.get("patterns", []))
        quality = evidence_pack.get("scoring", {}).get("evidence_quality", 0)

        summary = (
            f"Evidence pack contains {scans_count} completed scans with "
            f"{evidence_count} evidence items and {patterns_count} identified patterns. "
            f"Overall evidence quality score: {quality:.1f}/100. "
        )

        # Add pattern insights
        patterns = evidence_pack.get("patterns", [])
        for pattern in patterns[:2]:
            summary += f"{pattern.get('description')}. "

        return summary.strip()

    @cache_result(duration=3600, key_prefix="evidence_pack")
    def retrieve_evidence_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored evidence pack."""
        try:
            doc = frappe.get_doc("Internal Evidence Pack", pack_id)
            return {
                "pack_id": doc.name,
                "evidence_data": doc.evidence_data,
                "created": doc.creation,
                "created_by": doc.owner,
            }
        except frappe.DoesNotExistError:
            return None

    def store_evidence_pack(
        self, 
        pack_data: Dict[str, Any], 
        intent: str, 
        owner: str = None
    ) -> str:
        """Store evidence pack in database."""
        import json

        pack_id = self._generate_pack_id()
        owner = owner or frappe.session.user

        try:
            doc = frappe.new_doc("Internal Evidence Pack")
            doc.name = pack_id
            doc.intent = intent
            doc.evidence_data = json.dumps(pack_data)
            doc.owner = owner
            doc.insert(ignore_permissions=True)

            return pack_id
        except Exception as e:
            frappe.logger().error(f"Failed to store evidence pack: {e}")
            raise AnalysisError(f"Failed to store evidence pack: {str(e)}")

    def _generate_pack_id(self) -> str:
        """Generate unique evidence pack ID."""
        from datetime import datetime
        import uuid

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"EVD-{timestamp}-{unique_id}"

    def get_pack_statistics(self, evidence_pack: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about an evidence pack."""
        return {
            "scans_performed": len(evidence_pack.get("scans", [])),
            "evidence_items": len(evidence_pack.get("evidence_items", [])),
            "patterns_identified": len(evidence_pack.get("patterns", [])),
            "high_severity_alerts": sum(
                1 for item in evidence_pack.get("evidence_items", [])
                if item.get("severity") == AlertSeverity.HIGH.value
            ),
            "overall_quality": evidence_pack.get("scoring", {}).get("evidence_quality", 0),
        }
