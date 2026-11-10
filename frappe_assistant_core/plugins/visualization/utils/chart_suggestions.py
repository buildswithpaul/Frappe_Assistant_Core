# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Chart Suggestions Utility

AI-powered chart recommendation engine that analyzes data characteristics
and suggests optimal visualization approaches.
"""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from ..constants.viz_definitions import AGGREGATION_METHODS, CHART_TYPES


class ChartSuggestionEngine:
    """
    Intelligent chart suggestion engine that analyzes data patterns
    and recommends optimal visualizations.
    """

    def __init__(self):
        self.suggestion_rules = self._load_suggestion_rules()

    def suggest_charts_for_data(
        self, doctype: str, fields: List[str], data_sample: List[Dict], user_intent: str = ""
    ) -> List[Dict[str, Any]]:
        """Generate chart suggestions based on data analysis"""
        try:
            # Analyze field characteristics
            field_analysis = self._analyze_fields(doctype, fields, data_sample)

            # Generate suggestions based on field types
            suggestions = []

            # Single field suggestions
            for field_name, field_info in field_analysis.items():
                single_field_suggestions = self._suggest_single_field_charts(field_name, field_info)
                suggestions.extend(single_field_suggestions)

            # Multi-field suggestions
            multi_field_suggestions = self._suggest_multi_field_charts(field_analysis, data_sample)
            suggestions.extend(multi_field_suggestions)

            # Apply user intent filtering
            if user_intent:
                suggestions = self._filter_by_intent(suggestions, user_intent)

            # Rank and prioritize suggestions
            ranked_suggestions = self._rank_suggestions(suggestions, field_analysis, data_sample)

            return ranked_suggestions[:10]  # Return top 10 suggestions

        except Exception as e:
            frappe.logger("chart_suggestions").error(f"Chart suggestion failed: {str(e)}")
            return []

    def _analyze_fields(self, doctype: str, fields: List[str], data_sample: List[Dict]) -> Dict[str, Dict]:
        """Analyze field characteristics from data sample"""
        try:
            import pandas as pd

            field_analysis = {}

            if not data_sample:
                return field_analysis

            # frappe._dict answers any attribute with None, so pandas would take the rows for an array
            df = pd.DataFrame([dict(row) if isinstance(row, dict) else row for row in data_sample])

            for field in fields:
                if field not in df.columns:
                    continue

                series = df[field]
                analysis = {
                    "field_name": field,
                    "data_type": str(series.dtype),
                    "null_count": series.isnull().sum(),
                    "null_percentage": (series.isnull().sum() / len(series)) * 100,
                    "unique_count": series.nunique(),
                    "unique_percentage": (series.nunique() / len(series)) * 100,
                    "sample_values": series.dropna().head(5).tolist(),
                }

                # Determine field category
                analysis["category"] = self._determine_field_category(field, series, doctype)

                # Category-specific analysis
                if analysis["category"] == "numeric":
                    analysis.update(self._analyze_numeric_field(series))
                elif analysis["category"] == "categorical":
                    analysis.update(self._analyze_categorical_field(series))
                elif analysis["category"] == "temporal":
                    analysis.update(self._analyze_temporal_field(series))

                field_analysis[field] = analysis

            return field_analysis

        except Exception as e:
            frappe.logger("chart_suggestions").error(f"Field analysis failed: {str(e)}")
            return {}

    def _determine_field_category(self, field_name: str, series, doctype: str) -> str:
        """Determine the category of a field"""
        try:
            import pandas as pd

            # Get field metadata from DocType
            meta = frappe.get_meta(doctype)
            field_meta = None

            for df in meta.fields:
                if df.fieldname == field_name:
                    field_meta = df
                    break

            if field_meta:
                if field_meta.fieldtype in ["Int", "Float", "Currency", "Percent"]:
                    return "numeric"
                elif field_meta.fieldtype in ["Date", "Datetime", "Time"]:
                    return "temporal"
                elif field_meta.fieldtype in ["Select", "Link", "Data"]:
                    return "categorical"

            # Fallback to data-based detection
            if pd.api.types.is_numeric_dtype(series):
                return "numeric"
            elif pd.api.types.is_datetime64_any_dtype(series):
                return "temporal"
            else:
                return "categorical"

        except Exception:
            return "categorical"  # Safe fallback

    def _analyze_numeric_field(self, series) -> Dict[str, Any]:
        """Analyze numeric field characteristics"""
        try:
            import numpy as np
            import pandas as pd

            numeric_series = pd.to_numeric(series, errors="coerce")

            return {
                "min_value": float(numeric_series.min()),
                "max_value": float(numeric_series.max()),
                "mean_value": float(numeric_series.mean()),
                "median_value": float(numeric_series.median()),
                "std_deviation": float(numeric_series.std()),
                "has_zeros": (numeric_series == 0).any(),
                "has_negatives": (numeric_series < 0).any(),
                "distribution_type": self._detect_distribution_type(numeric_series),
            }

        except Exception:
            return {}

    def _analyze_categorical_field(self, series) -> Dict[str, Any]:
        """Analyze categorical field characteristics"""
        try:
            value_counts = series.value_counts()

            return {
                "top_categories": value_counts.head(10).to_dict(),
                "category_count": len(value_counts),
                "most_common": value_counts.index[0] if not value_counts.empty else None,
                "distribution_evenness": self._calculate_distribution_evenness(value_counts),
                "has_long_tail": len(value_counts) > 20
                and value_counts.iloc[10:].sum() < value_counts.iloc[:10].sum() * 0.1,
            }

        except Exception:
            return {}

    def _analyze_temporal_field(self, series) -> Dict[str, Any]:
        """Analyze temporal field characteristics"""
        try:
            import pandas as pd

            date_series = pd.to_datetime(series, errors="coerce")
            date_series = date_series.dropna()

            if date_series.empty:
                return {}

            return {
                "min_date": date_series.min().isoformat(),
                "max_date": date_series.max().isoformat(),
                "date_range_days": (date_series.max() - date_series.min()).days,
                "has_time_component": any(date_series.dt.time != pd.Timestamp("00:00:00").time()),
                "frequency_pattern": self._detect_date_frequency(date_series),
            }

        except Exception:
            return {}

    def _detect_distribution_type(self, numeric_series) -> str:
        """Detect the distribution type of numeric data"""
        try:
            import numpy as np
            import scipy.stats as stats

            # Remove NaN values
            clean_data = numeric_series.dropna()

            if len(clean_data) < 10:
                return "insufficient_data"

            # Test for normality
            _, p_normal = stats.normaltest(clean_data)
            if p_normal > 0.05:
                return "normal"

            # Check for uniform distribution
            _, p_uniform = stats.kstest(clean_data, "uniform")
            if p_uniform > 0.05:
                return "uniform"

            # Check skewness
            skewness = stats.skew(clean_data)
            if skewness > 1:
                return "right_skewed"
            elif skewness < -1:
                return "left_skewed"

            return "unknown"

        except Exception:
            return "unknown"

    def _calculate_distribution_evenness(self, value_counts) -> float:
        """Calculate how evenly distributed categorical values are"""
        try:
            if len(value_counts) <= 1:
                return 1.0

            # Calculate entropy-based evenness
            import numpy as np

            proportions = value_counts / value_counts.sum()
            entropy = -sum(p * np.log(p) for p in proportions if p > 0)
            max_entropy = np.log(len(value_counts))

            return entropy / max_entropy if max_entropy > 0 else 0

        except Exception:
            return 0.5  # Default moderate evenness

    def _detect_date_frequency(self, date_series) -> str:
        """Detect the frequency pattern of dates"""
        try:
            if len(date_series) < 3:
                return "irregular"

            # Sort dates
            sorted_dates = date_series.sort_values()

            # Calculate differences
            diffs = sorted_dates.diff().dropna()

            # Get most common difference
            most_common_diff = diffs.mode().iloc[0] if not diffs.empty else None

            if most_common_diff is None:
                return "irregular"

            days = most_common_diff.days

            if days == 1:
                return "daily"
            elif 6 <= days <= 8:
                return "weekly"
            elif 28 <= days <= 32:
                return "monthly"
            elif 88 <= days <= 95:
                return "quarterly"
            elif 360 <= days <= 370:
                return "yearly"
            else:
                return "irregular"

        except Exception:
            return "irregular"

    def _suggest_single_field_charts(self, field_name: str, field_info: Dict) -> List[Dict[str, Any]]:
        """Suggest charts for single field analysis"""
        suggestions = []
        category = field_info.get("category", "categorical")

        try:
            if category == "numeric":
                # Histogram for distribution
                suggestions.append(
                    {
                        "chart_type": "histogram",
                        "title": f"{field_name} Distribution",
                        "y_field": field_name,
                        "rationale": "Shows the distribution pattern of numeric values",
                        "priority": "medium",
                        "confidence": 0.8,
                    }
                )

                # Box plot for statistical summary
                suggestions.append(
                    {
                        "chart_type": "box",
                        "title": f"{field_name} Statistics",
                        "y_field": field_name,
                        "rationale": "Displays statistical summary and identifies outliers",
                        "priority": "low",
                        "confidence": 0.7,
                    }
                )

            elif category == "categorical":
                unique_count = field_info.get("unique_count", 0)

                if unique_count <= 10:
                    # Pie chart for small number of categories
                    suggestions.append(
                        {
                            "chart_type": "pie",
                            "title": f"Distribution by {field_name}",
                            "x_field": field_name,
                            "y_field": "count",
                            "aggregate": "count",
                            "rationale": "Shows proportional breakdown of categories",
                            "priority": "high",
                            "confidence": 0.9,
                        }
                    )

                # Bar chart for category counts
                suggestions.append(
                    {
                        "chart_type": "bar",
                        "title": f"Count by {field_name}",
                        "x_field": field_name,
                        "y_field": "count",
                        "aggregate": "count",
                        "rationale": "Compares frequency across categories",
                        "priority": "high" if unique_count <= 20 else "medium",
                        "confidence": 0.8,
                    }
                )

            return suggestions

        except Exception as e:
            frappe.logger("chart_suggestions").error(f"Single field suggestion failed: {str(e)}")
            return []

    def _suggest_multi_field_charts(
        self, field_analysis: Dict, data_sample: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Suggest charts combining multiple fields"""
        suggestions = []

        try:
            numeric_fields = [
                name for name, info in field_analysis.items() if info.get("category") == "numeric"
            ]
            categorical_fields = [
                name for name, info in field_analysis.items() if info.get("category") == "categorical"
            ]
            temporal_fields = [
                name for name, info in field_analysis.items() if info.get("category") == "temporal"
            ]

            # Time series charts
            for temporal_field in temporal_fields:
                for numeric_field in numeric_fields:
                    suggestions.append(
                        {
                            "chart_type": "line",
                            "title": f"{numeric_field} over {temporal_field}",
                            "x_field": temporal_field,
                            "y_field": numeric_field,
                            "aggregate": "sum",
                            "rationale": "Tracks trends and changes over time",
                            "priority": "high",
                            "confidence": 0.9,
                        }
                    )

            # Categorical vs numeric comparisons
            for categorical_field in categorical_fields:
                cat_info = field_analysis[categorical_field]
                if cat_info.get("unique_count", 0) <= 20:  # Reasonable number of categories
                    for numeric_field in numeric_fields:
                        suggestions.append(
                            {
                                "chart_type": "bar",
                                "title": f"{numeric_field} by {categorical_field}",
                                "x_field": categorical_field,
                                "y_field": numeric_field,
                                "aggregate": "sum",
                                "rationale": "Compares numeric values across categories",
                                "priority": "high",
                                "confidence": 0.8,
                            }
                        )

            # Numeric correlations
            if len(numeric_fields) >= 2:
                for i, field1 in enumerate(numeric_fields):
                    for field2 in numeric_fields[i + 1 :]:
                        suggestions.append(
                            {
                                "chart_type": "scatter",
                                "title": f"{field1} vs {field2}",
                                "x_field": field1,
                                "y_field": field2,
                                "rationale": "Explores correlation between numeric variables",
                                "priority": "medium",
                                "confidence": 0.7,
                            }
                        )

            return suggestions

        except Exception as e:
            frappe.logger("chart_suggestions").error(f"Multi-field suggestion failed: {str(e)}")
            return []

    def _filter_by_intent(self, suggestions: List[Dict], user_intent: str) -> List[Dict]:
        """Filter suggestions based on user intent"""
        try:
            intent_lower = user_intent.lower()

            # Intent-based filtering
            if any(word in intent_lower for word in ["trend", "time", "over time", "historical"]):
                # Prioritize time-series charts
                return [s for s in suggestions if s.get("chart_type") in ["line", "area"]]

            elif any(word in intent_lower for word in ["compare", "comparison", "vs", "versus"]):
                # Prioritize comparison charts
                return [s for s in suggestions if s.get("chart_type") in ["bar", "column"]]

            elif any(word in intent_lower for word in ["proportion", "percentage", "share", "breakdown"]):
                # Prioritize proportion charts
                return [s for s in suggestions if s.get("chart_type") in ["pie", "donut"]]

            elif any(word in intent_lower for word in ["correlation", "relationship", "pattern"]):
                # Prioritize correlation charts
                return [s for s in suggestions if s.get("chart_type") in ["scatter", "heatmap"]]

            elif any(word in intent_lower for word in ["distribution", "spread", "range"]):
                # Prioritize distribution charts
                return [s for s in suggestions if s.get("chart_type") in ["histogram", "box"]]

            return suggestions

        except Exception:
            return suggestions

    def _rank_suggestions(
        self, suggestions: List[Dict], field_analysis: Dict, data_sample: List[Dict]
    ) -> List[Dict]:
        """Rank suggestions by relevance and quality"""
        try:
            for suggestion in suggestions:
                score = 0

                # Base score from confidence
                score += suggestion.get("confidence", 0.5) * 40

                # Priority bonus
                priority = suggestion.get("priority", "medium")
                if priority == "high":
                    score += 30
                elif priority == "medium":
                    score += 20
                else:
                    score += 10

                # Data compatibility score
                chart_type = suggestion.get("chart_type")
                x_field = suggestion.get("x_field")
                y_field = suggestion.get("y_field")

                # Check field compatibility
                if x_field and x_field in field_analysis:
                    x_info = field_analysis[x_field]
                    score += self._calculate_field_compatibility_score(chart_type, x_info, "x")

                if y_field and y_field in field_analysis:
                    y_info = field_analysis[y_field]
                    score += self._calculate_field_compatibility_score(chart_type, y_info, "y")

                # Data size penalty for inappropriate charts
                data_count = len(data_sample)
                if chart_type == "pie" and data_count > 100:
                    score -= 10  # Too many data points for pie chart
                elif chart_type == "scatter" and data_count < 10:
                    score -= 15  # Too few points for scatter plot

                suggestion["score"] = max(0, score)

            # Sort by score
            return sorted(suggestions, key=lambda x: x.get("score", 0), reverse=True)

        except Exception as e:
            frappe.logger("chart_suggestions").error(f"Ranking failed: {str(e)}")
            return suggestions

    def _calculate_field_compatibility_score(self, chart_type: str, field_info: Dict, axis: str) -> float:
        """Calculate how well a field fits with a chart type"""
        try:
            field_category = field_info.get("category", "categorical")

            # Chart type requirements
            compatibility_matrix = {
                "bar": {"x": ["categorical"], "y": ["numeric"]},
                "line": {"x": ["temporal", "numeric"], "y": ["numeric"]},
                "pie": {"x": ["categorical"], "y": ["numeric"]},
                "scatter": {"x": ["numeric"], "y": ["numeric"]},
                "histogram": {"y": ["numeric"]},
                "box": {"y": ["numeric"]},
                "heatmap": {"x": ["categorical"], "y": ["categorical"]},
            }

            if chart_type in compatibility_matrix:
                required_types = compatibility_matrix[chart_type].get(axis, [])
                if field_category in required_types:
                    return 15
                else:
                    return -5

            return 0

        except Exception:
            return 0

    def _load_suggestion_rules(self) -> Dict[str, Any]:
        """Load chart suggestion rules"""
        return {
            "time_series_indicators": ["date", "time", "created", "modified", "posting_date"],
            "categorical_indicators": ["type", "status", "category", "group", "classification"],
            "numeric_indicators": ["amount", "total", "value", "count", "quantity", "rate"],
            "preferred_combinations": {
                ("temporal", "numeric"): "line",
                ("categorical", "numeric"): "bar",
                ("numeric", "numeric"): "scatter",
            },
        }


# Factory function to create suggestion engine
def create_suggestion_engine() -> ChartSuggestionEngine:
    """Create and return a chart suggestion engine instance"""
    return ChartSuggestionEngine()


# Convenience function for quick suggestions
def get_chart_suggestions(
    doctype: str, fields: List[str], data_sample: List[Dict] = None, user_intent: str = ""
) -> List[Dict[str, Any]]:
    """Get chart suggestions for given data"""
    try:
        engine = create_suggestion_engine()

        # Get data sample if not provided
        if data_sample is None:
            data_sample = frappe.get_all(doctype, fields=fields, limit=100, order_by="creation desc")

        return engine.suggest_charts_for_data(doctype, fields, data_sample, user_intent)

    except Exception as e:
        frappe.logger("chart_suggestions").error(f"Quick suggestions failed: {str(e)}")
        return []


# Export functions
__all__ = ["ChartSuggestionEngine", "create_suggestion_engine", "get_chart_suggestions"]
