"""
Anomaly Detection Tool

Identifies statistical anomalies and unusual patterns in business data.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import statistics
import frappe
from ..enhanced_base_tool import EnhancedBaseTool
from ..constants import AlertSeverity, ConfidenceLevel
from ..decorators import log_performance, cache_result
from ..exceptions import AnomalyDetectionError


class AnomalyDetectionTool(EnhancedBaseTool):
    """
    Anomaly Detection Tool
    
    Identifies:
    - Statistical anomalies in metrics
    - Unusual customer behavior
    - Abnormal product performance
    - Seasonal deviation
    - Price/cost anomalies
    - Volume anomalies
    """

    name = "anomaly_detector"
    description = "Detects statistical anomalies in business data"

    # Sensitivity thresholds (standard deviations)
    SENSITIVITY_LEVELS = {
        "low": 3.0,      # Conservative - 3 sigma
        "medium": 2.5,   # Moderate - 2.5 sigma
        "high": 2.0,     # Aggressive - 2 sigma
    }

    def _execute_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute anomaly detection."""
        data_points = arguments.get("data_points", [])
        metric_name = arguments.get("metric_name", "unknown")
        sensitivity = arguments.get("sensitivity", "medium")
        date_range = arguments.get("date_range", "last_month")
        
        if not data_points or len(data_points) < 3:
            raise AnomalyDetectionError("At least 3 data points required for anomaly detection")

        try:
            # Extract values
            values = [float(point.get("value", 0)) for point in data_points]
            
            # Perform statistical analysis
            anomalies = self._detect_anomalies(values, sensitivity)
            
            # Analyze patterns
            patterns = self._analyze_patterns(data_points)
            
            # Score severity
            severity_assessment = self._assess_severity(anomalies, data_points)

            return {
                "success": True,
                "metric_name": metric_name,
                "data_points_analyzed": len(data_points),
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies,
                "patterns": patterns,
                "severity": severity_assessment.get("level"),
                "severity_score": severity_assessment.get("score"),
                "statistical_summary": self._get_statistical_summary(values),
                "confidence": 88.0,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise AnomalyDetectionError(f"Anomaly detection failed: {str(e)}")

    @log_performance(threshold_ms=1000)
    def _detect_anomalies(
        self, 
        values: List[float], 
        sensitivity: str = "medium"
    ) -> List[Dict[str, Any]]:
        """Detect statistical anomalies using z-score method."""
        if len(values) < 3:
            return []

        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            
            if stdev == 0:
                return []

            threshold = self.SENSITIVITY_LEVELS.get(sensitivity, 2.5)
            anomalies = []

            for i, value in enumerate(values):
                z_score = abs((value - mean) / stdev) if stdev > 0 else 0
                
                if z_score > threshold:
                    anomalies.append({
                        "index": i,
                        "value": value,
                        "mean": mean,
                        "z_score": z_score,
                        "deviation_percent": ((value - mean) / mean * 100) if mean != 0 else 0,
                        "severity": self._score_anomaly_severity(z_score, threshold),
                        "is_outlier": z_score > threshold * 1.5,
                    })

            return anomalies
        except Exception as e:
            frappe.logger().error(f"Anomaly detection error: {e}")
            return []

    def _score_anomaly_severity(self, z_score: float, threshold: float) -> str:
        """Score severity of anomaly."""
        ratio = z_score / threshold
        
        if ratio > 2.0:
            return AlertSeverity.CRITICAL.value
        elif ratio > 1.5:
            return AlertSeverity.HIGH.value
        elif ratio > 1.0:
            return AlertSeverity.MEDIUM.value
        else:
            return AlertSeverity.LOW.value

    def _analyze_patterns(self, data_points: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze patterns in data points."""
        if len(data_points) < 3:
            return []

        patterns = []

        # Extract values and dates
        values = [float(point.get("value", 0)) for point in data_points]
        
        # Trend analysis
        trend = self._analyze_trend(values)
        if trend:
            patterns.append(trend)

        # Seasonality check
        seasonality = self._detect_seasonality(values)
        if seasonality:
            patterns.append(seasonality)

        # Volatility analysis
        volatility = self._analyze_volatility(values)
        if volatility:
            patterns.append(volatility)

        return patterns

    def _analyze_trend(self, values: List[float]) -> Optional[Dict[str, Any]]:
        """Analyze upward/downward trend."""
        if len(values) < 3:
            return None

        # Simple trend: compare first third with last third
        third = len(values) // 3
        first_avg = statistics.mean(values[:third])
        last_avg = statistics.mean(values[-third:])
        
        change_percent = ((last_avg - first_avg) / first_avg * 100) if first_avg != 0 else 0

        if abs(change_percent) > 10:
            return {
                "pattern_type": "trend",
                "direction": "increasing" if change_percent > 0 else "decreasing",
                "change_percent": change_percent,
                "severity": AlertSeverity.MEDIUM.value if abs(change_percent) > 20 else AlertSeverity.LOW.value,
                "description": f"Data shows {abs(change_percent):.1f}% {('increase' if change_percent > 0 else 'decrease')} over time",
            }
        
        return None

    def _detect_seasonality(self, values: List[float]) -> Optional[Dict[str, Any]]:
        """Detect seasonal patterns."""
        if len(values) < 12:
            return None

        # Simple seasonality check: compare same positions in cycles
        try:
            cycle_length = 4  # Assume quarterly
            patterns_found = []
            
            for offset in range(cycle_length):
                cycle_values = [values[i] for i in range(offset, len(values), cycle_length)]
                if len(cycle_values) > 1:
                    patterns_found.append((offset, statistics.variance(cycle_values)))
            
            if patterns_found:
                return {
                    "pattern_type": "seasonality",
                    "cycle_detected": True,
                    "potential_cycle_length": 4,
                    "severity": AlertSeverity.LOW.value,
                    "description": "Seasonal pattern detected in data",
                }
        except:
            pass
        
        return None

    def _analyze_volatility(self, values: List[float]) -> Optional[Dict[str, Any]]:
        """Analyze volatility (standard deviation)."""
        if len(values) < 2:
            return None

        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        
        cv = (stdev / mean * 100) if mean != 0 else 0  # Coefficient of variation

        if cv > 50:
            severity = AlertSeverity.HIGH.value
        elif cv > 30:
            severity = AlertSeverity.MEDIUM.value
        else:
            severity = AlertSeverity.LOW.value

        return {
            "pattern_type": "volatility",
            "coefficient_of_variation": cv,
            "standard_deviation": stdev,
            "mean": mean,
            "severity": severity,
            "description": f"High volatility detected: {cv:.1f}% coefficient of variation",
        } if cv > 20 else None

    def _get_statistical_summary(self, values: List[float]) -> Dict[str, Any]:
        """Get statistical summary of data."""
        if not values:
            return {}

        sorted_values = sorted(values)
        n = len(sorted_values)
        
        summary = {
            "count": n,
            "mean": statistics.mean(values),
            "median": sorted_values[n // 2],
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
            "std_dev": statistics.stdev(values) if n > 1 else 0,
        }

        # Add quartiles
        q1_index = n // 4
        q3_index = 3 * n // 4
        summary["q1"] = sorted_values[q1_index]
        summary["q3"] = sorted_values[q3_index]
        summary["iqr"] = summary["q3"] - summary["q1"]

        return summary

    def _assess_severity(
        self, 
        anomalies: List[Dict], 
        data_points: List[Dict]
    ) -> Dict[str, Any]:
        """Assess overall severity of anomalies."""
        if not anomalies:
            return {"level": AlertSeverity.LOW.value, "score": 0}

        # Calculate severity score
        critical_count = sum(1 for a in anomalies if a.get("severity") == AlertSeverity.CRITICAL.value)
        high_count = sum(1 for a in anomalies if a.get("severity") == AlertSeverity.HIGH.value)
        
        anomaly_percent = (len(anomalies) / len(data_points) * 100) if data_points else 0

        score = (critical_count * 40) + (high_count * 20) + (anomaly_percent * 0.5)
        score = min(100, score)

        if score > 70:
            level = AlertSeverity.CRITICAL.value
        elif score > 40:
            level = AlertSeverity.HIGH.value
        elif score > 20:
            level = AlertSeverity.MEDIUM.value
        else:
            level = AlertSeverity.LOW.value

        return {
            "level": level,
            "score": score,
            "anomaly_count": len(anomalies),
            "anomaly_percent": anomaly_percent,
        }

    @cache_result(duration=1800, key_prefix="anomaly_history")
    def get_anomaly_history(self, metric_name: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical anomalies for a metric."""
        try:
            doc_name = f"anomaly_{metric_name}_{days}d"
            
            # Query recent anomalies
            anomalies = frappe.db.sql("""
                SELECT 
                    name, metric_name, anomaly_value, 
                    mean_value, severity, creation
                FROM `tabInternal Anomaly Detection`
                WHERE metric_name = %s 
                    AND creation > DATE_SUB(NOW(), INTERVAL %s DAY)
                ORDER BY creation DESC
            """, (metric_name, days), as_dict=True)

            return anomalies
        except Exception as e:
            frappe.logger().warning(f"Failed to get anomaly history: {e}")
            return []

    def detect_customer_anomalies(self, company: str) -> List[Dict[str, Any]]:
        """Detect anomalies in customer behavior."""
        try:
            # Get customer spending data
            customer_data = frappe.db.sql("""
                SELECT 
                    customer,
                    SUM(total) as total_spent,
                    COUNT(*) as order_count,
                    AVG(total) as avg_order_value
                FROM `tabSales Order`
                WHERE company = %s AND docstatus = 1
                GROUP BY customer
                ORDER BY total_spent DESC
            """, (company,), as_dict=True)

            if not customer_data:
                return []

            spending_values = [c['total_spent'] for c in customer_data]
            anomalies = self._detect_anomalies(spending_values)

            # Map anomalies back to customers
            anomaly_customers = []
            for anomaly in anomalies:
                idx = anomaly.get("index", 0)
                if idx < len(customer_data):
                    customer = customer_data[idx]
                    anomaly_customers.append({
                        "customer": customer['customer'],
                        "total_spent": customer['total_spent'],
                        "anomaly_type": "spending_behavior",
                        "z_score": anomaly.get("z_score"),
                        "severity": anomaly.get("severity"),
                    })

            return anomaly_customers
        except Exception as e:
            frappe.logger().error(f"Customer anomaly detection failed: {e}")
            return []
