"""
Enterprise Scanner Plugin

Main plugin that orchestrates the scanning, analysis, and recommendation process.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import frappe
from ..enhanced_base_plugin import EnhancedBasePlugin
from ..constants import DecisionIntentType, ScanType, DecisionStatus
from ..decorators import log_performance, track_metrics
from .decision_intent_analyzer import DecisionIntentAnalyzerTool
from .enterprise_scanner_engine import EnterpriseScanner
from .data_source_mapper import DataSourceMapper
from .evidence_collector import EvidenceCollector


class EnterpriseScannerPlugin(EnhancedBasePlugin):
    """
    Enterprise Scanner Plugin
    
    Orchestrates the complete scanning and intelligence pipeline:
    1. Analyzes user intent
    2. Performs targeted scans
    3. Maps data to standardized format
    4. Collects and scores evidence
    5. Generates recommendations
    """

    def __init__(self):
        super().__init__()
        self.intent_analyzer = None
        self.scanner = None
        self.data_mapper = None
        self.evidence_collector = None
        self.active_scans = {}

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": "enterprise_scanner",
            "display_name": "Enterprise Scanner Plugin",
            "version": "1.0.0",
            "description": "Analyzes business data and provides intelligent recommendations",
            "author": "Frappe Assistant Core Team",
            "dependencies": ["frappe", "frappe_assistant_core"],
        }

    def validate_environment(self) -> tuple:
        """Validate plugin environment."""
        try:
            # Check Frappe installation
            import frappe
            if not frappe.db:
                return False, "Frappe database not accessible"

            # Check required doctypes exist
            required_doctypes = [
                "Sales Order", "Customer", "Item", "Purchase Order"
            ]
            for doctype in required_doctypes:
                if not frappe.db.exists("DocType", doctype):
                    return False, f"Required doctype '{doctype}' not found"

            return True, None
        except Exception as e:
            return False, str(e)

    def get_tools(self) -> List[str]:
        """Get available tools in this plugin."""
        return [
            "decision_intent_analyzer",
            "enterprise_scanner",
            "data_source_mapper",
            "evidence_collector",
        ]

    def on_enable(self) -> None:
        """Initialize tools when plugin is enabled."""
        try:
            self.intent_analyzer = DecisionIntentAnalyzerTool()
            self.scanner = EnterpriseScanner()
            self.data_mapper = DataSourceMapper()
            self.evidence_collector = EvidenceCollector()
            frappe.logger().info("Enterprise Scanner tools initialized")
        except Exception as e:
            frappe.logger().error(f"Failed to initialize tools: {e}")
            raise

    def on_disable(self) -> None:
        """Cleanup when plugin is disabled."""
        self.intent_analyzer = None
        self.scanner = None
        self.data_mapper = None
        self.evidence_collector = None
        frappe.logger().info("Enterprise Scanner tools uninitialized")

    @log_performance(threshold_ms=5000)
    @track_metrics(metric_prefix="enterprise_scanner")
    def analyze_decision(self, user_input: str, company: str = None) -> Dict[str, Any]:
        """
        Analyze a business decision and provide intelligence.
        
        Args:
            user_input: User's business question/decision
            company: Company to analyze (defaults to user's default company)
            
        Returns:
            Complete intelligence analysis with recommendations
        """
        company = company or frappe.defaults.get_user_default("company")
        
        try:
            # Step 1: Analyze intent
            intent_result = self.intent_analyzer.execute({
                "user_input": user_input
            })

            if not intent_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to analyze intent",
                }

            intent_type = intent_result.get("intent")
            required_scans = intent_result.get("required_scans", [])

            # Step 2: Execute scans
            scan_results = []
            for scan_type in required_scans[:5]:  # Limit to 5 scans
                try:
                    scan_result = self.scanner.execute({
                        "scan_type": scan_type,
                        "company": company,
                        "date_range": "last_month"
                    })
                    if scan_result.get("success"):
                        scan_results.append(scan_result)
                except Exception as e:
                    frappe.logger().warning(f"Scan {scan_type} failed: {e}")

            if not scan_results:
                return {
                    "success": False,
                    "error": "No scans completed successfully",
                }

            # Step 3: Collect evidence
            evidence_result = self.evidence_collector.execute({
                "scan_results": scan_results,
                "intent": intent_type,
                "date_range": "last_month"
            })

            if not evidence_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to collect evidence",
                }

            evidence_pack = evidence_result.get("evidence_pack", {})

            # Step 4: Generate recommendations
            recommendations = self._generate_recommendations(
                evidence_pack, 
                intent_type,
                scan_results
            )

            # Step 5: Create intelligence report
            report = {
                "success": True,
                "analysis_timestamp": datetime.now().isoformat(),
                "decision_intent": intent_type,
                "intent_confidence": intent_result.get("intent_confidence", 0),
                "scans_performed": len(scan_results),
                "evidence_quality": evidence_pack.get("scoring", {}).get("evidence_quality", 0),
                "patterns_identified": len(evidence_pack.get("patterns", [])),
                "recommendations": recommendations,
                "evidence_summary": evidence_pack.get("summary", ""),
                "key_metrics": self._extract_key_metrics(scan_results),
                "alerts": self._extract_alerts(evidence_pack),
                "business_areas": intent_result.get("business_areas", []),
            }

            # Store report
            self._store_analysis_report(report, company)

            return report

        except Exception as e:
            frappe.logger().error(f"Decision analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _generate_recommendations(
        self,
        evidence_pack: Dict[str, Any],
        intent: str,
        scan_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on evidence."""
        recommendations = []

        patterns = evidence_pack.get("patterns", [])
        
        for pattern in patterns:
            pattern_type = pattern.get("pattern")
            
            if pattern_type == "concentration_dependency":
                recommendations.append({
                    "priority": "high",
                    "category": "Risk Mitigation",
                    "title": "Diversify Customer/Product Base",
                    "description": (
                        f"Current concentration risk is {pattern.get('average_concentration', 0):.1f}%. "
                        "Consider diversification strategies to reduce dependency."
                    ),
                    "impact": "Reduces business vulnerability to single customer/product loss",
                    "timeline": "6-12 months",
                })

            elif pattern_type == "growth_trajectory":
                growth = pattern.get("average_growth", 0)
                if growth < -5:
                    recommendations.append({
                        "priority": "high",
                        "category": "Performance",
                        "title": "Address Declining Sales",
                        "description": f"Sales declining at {abs(growth):.1f}% monthly. Immediate action required.",
                        "impact": "Stabilize revenue and identify root causes",
                        "timeline": "1-3 months",
                    })
                elif growth > 10:
                    recommendations.append({
                        "priority": "medium",
                        "category": "Opportunity",
                        "title": "Capitalize on Growth Momentum",
                        "description": f"Strong growth of {growth:.1f}% monthly. Allocate resources to scale.",
                        "impact": "Accelerate market expansion and revenue growth",
                        "timeline": "3-6 months",
                    })

            elif pattern_type == "high_risk_indicators":
                recommendations.append({
                    "priority": "critical",
                    "category": "Risk Mitigation",
                    "title": "Address High-Risk Indicators",
                    "description": (
                        f"Identified {pattern.get('count', 0)} high-risk indicators requiring attention."
                    ),
                    "impact": "Prevent potential business disruption",
                    "timeline": "Immediate",
                })

        # Add intent-specific recommendations
        if intent == "cost_optimization":
            recommendations.append({
                "priority": "high",
                "category": "Cost Optimization",
                "title": "Implement Cost Reduction Program",
                "description": "Review supplier contracts and operational efficiencies",
                "impact": "Potential 10-15% cost reduction",
                "timeline": "3-6 months",
            })

        return recommendations

    def _extract_key_metrics(self, scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key metrics from scan results."""
        metrics = {}

        for scan in scan_results:
            scan_type = scan.get("scan_type")
            summary = scan.get("summary", {})

            if scan_type == "customers":
                metrics["customer_concentration"] = summary.get("top_3_concentration", "N/A")
                metrics["total_customers"] = summary.get("total_customers", 0)

            elif scan_type == "sales":
                metrics["monthly_growth"] = summary.get("growth_rate", "N/A")
                metrics["sales_trend"] = summary.get("trend", "N/A")

            elif scan_type == "products":
                metrics["product_concentration"] = summary.get("top_10_concentration", "N/A")

        return metrics

    def _extract_alerts(self, evidence_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract alerts from evidence pack."""
        alerts = []

        for item in evidence_pack.get("evidence_items", []):
            if item.get("severity") in ["high", "critical"]:
                alerts.append({
                    "severity": item.get("severity"),
                    "type": item.get("type"),
                    "message": item.get("description"),
                    "metric": item.get("metric"),
                    "value": item.get("value"),
                })

        return alerts

    def _store_analysis_report(
        self,
        report: Dict[str, Any],
        company: str
    ) -> Optional[str]:
        """Store analysis report in database."""
        try:
            import json

            doc = frappe.new_doc("Internal Decision Analysis")
            doc.company = company
            doc.decision_intent = report.get("decision_intent")
            doc.analysis_data = json.dumps(report)
            doc.status = "completed"
            doc.user = frappe.session.user
            doc.insert(ignore_permissions=True)

            return doc.name
        except Exception as e:
            frappe.logger().warning(f"Failed to store analysis report: {e}")
            return None

    def get_active_scans(self) -> List[Dict[str, Any]]:
        """Get list of active scans."""
        return [
            {
                "scan_id": scan_id,
                "status": scan_info.get("status"),
                "started_at": scan_info.get("started_at"),
                "progress": scan_info.get("progress", 0),
            }
            for scan_id, scan_info in self.active_scans.items()
        ]

    def cancel_scan(self, scan_id: str) -> bool:
        """Cancel an active scan."""
        if scan_id in self.active_scans:
            del self.active_scans[scan_id]
            return True
        return False
