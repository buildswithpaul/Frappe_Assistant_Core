"""
Scenario Analyzer Tool

Analyzes business scenarios and their potential impacts on key metrics.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import frappe
from ..enhanced_base_tool import EnhancedBaseTool
from ..constants import AlertSeverity, ConfidenceLevel, ScenarioType
from ..decorators import log_performance, cache_result
from ..exceptions import ScenarioAnalysisError


class ScenarioAnalyzerTool(EnhancedBaseTool):
    """
    Scenario Analyzer Tool
    
    Analyzes business scenarios:
    - Best case scenarios
    - Worst case scenarios
    - Expected case scenarios
    - Custom scenarios
    - Impact analysis
    - Risk assessment
    - Opportunity identification
    """

    name = "scenario_analyzer"
    description = "Analyzes business scenarios and their potential impacts"

    # Scenario templates
    SCENARIO_TEMPLATES = {
        "market_expansion": {
            "name": "Market Expansion",
            "description": "Expanding into new geographic markets",
            "factors": {
                "customer_base": {"low": 0.8, "expected": 1.3, "high": 2.0},
                "sales_growth": {"low": 0.1, "expected": 0.35, "high": 0.6},
                "cost_increase": {"low": 1.2, "expected": 1.5, "high": 2.0},
            },
        },
        "cost_reduction": {
            "name": "Cost Reduction Program",
            "description": "Implementing operational efficiency initiatives",
            "factors": {
                "operational_cost": {"low": 0.85, "expected": 0.75, "high": 0.65},
                "profit_margin": {"low": 1.05, "expected": 1.15, "high": 1.25},
                "customer_satisfaction": {"low": 0.95, "expected": 1.0, "high": 1.05},
            },
        },
        "product_launch": {
            "name": "New Product Launch",
            "description": "Launching a new product line",
            "factors": {
                "revenue": {"low": 1.1, "expected": 1.4, "high": 2.0},
                "market_share": {"low": 1.05, "expected": 1.2, "high": 1.5},
                "customer_acquisition_cost": {"low": 1.1, "expected": 1.25, "high": 1.5},
            },
        },
        "partnership": {
            "name": "Strategic Partnership",
            "description": "Forming strategic partnerships",
            "factors": {
                "reach": {"low": 1.3, "expected": 1.6, "high": 2.2},
                "resource_efficiency": {"low": 0.9, "expected": 0.8, "high": 0.7},
                "integration_risk": {"low": 0.2, "expected": 0.35, "high": 0.5},
            },
        },
    }

    def _execute_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scenario analysis."""
        scenario_type = arguments.get("scenario_type")
        base_metrics = arguments.get("base_metrics", {})
        company = arguments.get("company")
        custom_factors = arguments.get("custom_factors")
        
        if not scenario_type or not base_metrics:
            raise ScenarioAnalysisError("scenario_type and base_metrics are required")

        try:
            # Get scenario template or use custom
            scenario = self._get_scenario(scenario_type, custom_factors)
            
            if not scenario:
                raise ScenarioAnalysisError(f"Unknown scenario type: {scenario_type}")

            # Generate scenarios
            scenarios = {
                "best_case": self._calculate_scenario(base_metrics, scenario, "high"),
                "expected_case": self._calculate_scenario(base_metrics, scenario, "expected"),
                "worst_case": self._calculate_scenario(base_metrics, scenario, "low"),
            }

            # Analyze impacts
            impact_analysis = self._analyze_impacts(scenarios, base_metrics)

            # Identify risks and opportunities
            risks = self._identify_risks(scenarios)
            opportunities = self._identify_opportunities(scenarios)

            return {
                "success": True,
                "scenario_type": scenario_type,
                "base_metrics": base_metrics,
                "scenarios": scenarios,
                "impact_analysis": impact_analysis,
                "risks": risks,
                "opportunities": opportunities,
                "recommendation": self._generate_recommendation(impact_analysis, risks),
                "confidence": 85.0,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise ScenarioAnalysisError(f"Scenario analysis failed: {str(e)}")

    def _get_scenario(
        self, 
        scenario_type: str, 
        custom_factors: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Get scenario template."""
        if custom_factors:
            return {
                "name": "Custom Scenario",
                "description": "Custom scenario with user-defined factors",
                "factors": custom_factors,
            }
        
        return self.SCENARIO_TEMPLATES.get(scenario_type)

    def _calculate_scenario(
        self, 
        base_metrics: Dict[str, Any], 
        scenario: Dict[str, Any], 
        case: str
    ) -> Dict[str, Any]:
        """Calculate metrics for a scenario case."""
        scenario_metrics = {
            "case": case,
            "metrics": {},
        }

        factors = scenario.get("factors", {})
        
        for metric_name, base_value in base_metrics.items():
            if metric_name in factors:
                multiplier = factors[metric_name].get(case, 1.0)
                new_value = base_value * multiplier
            else:
                new_value = base_value
            
            scenario_metrics["metrics"][metric_name] = new_value

        return scenario_metrics

    @log_performance(threshold_ms=2000)
    def _analyze_impacts(
        self, 
        scenarios: Dict[str, Dict], 
        base_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze impacts across scenarios."""
        impact_analysis = {
            "base_state": base_metrics,
            "scenario_changes": {},
        }

        for case_name, case_data in scenarios.items():
            changes = {}
            for metric, base_value in base_metrics.items():
                new_value = case_data.get("metrics", {}).get(metric, base_value)
                change = new_value - base_value
                change_percent = (change / base_value * 100) if base_value != 0 else 0
                
                changes[metric] = {
                    "base_value": base_value,
                    "new_value": new_value,
                    "change": change,
                    "change_percent": change_percent,
                }

            impact_analysis["scenario_changes"][case_name] = changes

        return impact_analysis

    def _identify_risks(self, scenarios: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Identify risks from worst case scenario."""
        risks = []
        worst_case = scenarios.get("worst_case", {})
        metrics = worst_case.get("metrics", {})

        # Analyze metric degradation
        for metric, value in metrics.items():
            if metric.lower() in ["revenue", "profit", "margin", "growth"]:
                if value < 0:  # Negative value
                    risks.append({
                        "type": "financial_risk",
                        "metric": metric,
                        "severity": AlertSeverity.HIGH.value,
                        "description": f"{metric} could turn negative in worst case",
                        "potential_value": value,
                    })
                elif "cost" in metric.lower() and value > 1.5:
                    risks.append({
                        "type": "cost_escalation_risk",
                        "metric": metric,
                        "severity": AlertSeverity.MEDIUM.value,
                        "description": f"{metric} could increase by {(value-1)*100:.0f}%",
                        "potential_value": value,
                    })

        return risks

    def _identify_opportunities(self, scenarios: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Identify opportunities from best case scenario."""
        opportunities = []
        best_case = scenarios.get("best_case", {})
        metrics = best_case.get("metrics", {})

        # Analyze metric improvements
        for metric, value in metrics.items():
            if metric.lower() in ["revenue", "profit", "market_share", "growth"]:
                improvement = value - 1  # Assuming base is 1.0
                if improvement > 0.2:  # 20% improvement or more
                    opportunities.append({
                        "type": "growth_opportunity",
                        "metric": metric,
                        "severity": AlertSeverity.INFO.value,
                        "description": f"Potential to increase {metric} by {improvement*100:.0f}%",
                        "potential_value": value,
                        "impact": "high" if improvement > 0.5 else "medium",
                    })

        return opportunities

    def _generate_recommendation(
        self, 
        impact_analysis: Dict[str, Any], 
        risks: List[Dict[str, Any]]
    ) -> str:
        """Generate recommendation based on analysis."""
        high_risk_count = sum(
            1 for risk in risks 
            if risk.get("severity") == AlertSeverity.HIGH.value
        )

        if high_risk_count >= 2:
            return (
                "Proceed with caution. Multiple high-risk factors identified. "
                "Develop mitigation strategies before implementation."
            )
        elif high_risk_count == 1:
            return (
                "Favorable scenario with manageable risks. "
                "Address identified risk factors in implementation plan."
            )
        else:
            return (
                "Strong positive outlook. Limited risks identified. "
                "Proceed with confidence, maintaining monitoring protocols."
            )

    @cache_result(duration=3600, key_prefix="scenario_analysis")
    def analyze_breakeven(
        self, 
        fixed_costs: float, 
        variable_cost_per_unit: float, 
        price_per_unit: float
    ) -> Dict[str, Any]:
        """Analyze break-even point."""
        if price_per_unit <= variable_cost_per_unit:
            return {
                "error": "Price must be higher than variable cost per unit",
            }

        contribution_margin = price_per_unit - variable_cost_per_unit
        breakeven_units = fixed_costs / contribution_margin
        breakeven_revenue = breakeven_units * price_per_unit

        return {
            "success": True,
            "breakeven_units": breakeven_units,
            "breakeven_revenue": breakeven_revenue,
            "contribution_margin_per_unit": contribution_margin,
            "contribution_margin_percent": (contribution_margin / price_per_unit) * 100,
            "summary": f"Need to sell {breakeven_units:.0f} units to break even",
        }

    @cache_result(duration=3600, key_prefix="scenario_roi")
    def calculate_roi(
        self, 
        investment: float, 
        expected_return: float, 
        timeframe_months: int = 12
    ) -> Dict[str, Any]:
        """Calculate return on investment."""
        roi_percent = (expected_return / investment) * 100 if investment > 0 else 0
        monthly_roi = roi_percent / timeframe_months
        
        return {
            "success": True,
            "investment": investment,
            "expected_return": expected_return,
            "roi_percent": roi_percent,
            "monthly_roi_percent": monthly_roi,
            "timeframe_months": timeframe_months,
            "payback_period_months": (investment / (expected_return / timeframe_months)) if expected_return > 0 else None,
        }

    def sensitivity_analysis(
        self, 
        base_value: float, 
        variable_name: str, 
        changes: List[float],
        impact_function
    ) -> List[Dict[str, Any]]:
        """Perform sensitivity analysis by varying one variable."""
        results = []

        for change in changes:
            new_value = base_value * (1 + change)
            impact = impact_function(new_value)
            
            results.append({
                "change_percent": change * 100,
                "new_value": new_value,
                "impact": impact,
            })

        return results

    def monte_carlo_simulation(
        self, 
        base_metrics: Dict[str, Any],
        probability_distributions: Dict[str, Tuple[float, float]],
        iterations: int = 1000
    ) -> Dict[str, Any]:
        """Simple Monte Carlo simulation for scenario outcomes."""
        import random

        results = []

        for _ in range(iterations):
            iteration_metrics = {}
            
            for metric, base_value in base_metrics.items():
                if metric in probability_distributions:
                    mean, stdev = probability_distributions[metric]
                    value = random.gauss(mean, stdev)
                else:
                    value = base_value
                
                iteration_metrics[metric] = value
            
            results.append(iteration_metrics)

        # Calculate statistics
        outcome_stats = {}
        for metric in base_metrics.keys():
            values = [r.get(metric, 0) for r in results]
            outcome_stats[metric] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std_dev": (sum((x - sum(values)/len(values))**2 for x in values) / len(values)) ** 0.5,
            }

        return {
            "success": True,
            "iterations": iterations,
            "outcome_statistics": outcome_stats,
            "simulation_results": results[:10],  # Return first 10 for brevity
        }
