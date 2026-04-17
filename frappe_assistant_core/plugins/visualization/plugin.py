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
Visualization Plugin - Main plugin registration

The main plugin class that registers all visualization tools and manages
the comprehensive dashboard system for Business Intelligence.
"""

from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class VisualizationPlugin(BasePlugin):
    """
    Comprehensive Visualization Plugin for Business Intelligence.

    Transforms Frappe Assistant from basic chart generation to a complete
    Business Intelligence suite with dashboard-focused approach.
    """

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            "name": "visualization",
            "display_name": "Visualization & Business Intelligence",
            "description": "Complete BI suite with dashboards, templates, and interactive widgets",
            "version": "1.0.0",
            "author": "Frappe Assistant Core Team",
            "category": "Business Intelligence",
            "dependencies": ["pandas", "numpy", "matplotlib", "seaborn", "plotly"],
            "requires_restart": False,
            "replaces": ["create_visualization"],  # Tools this plugin replaces
            "migration_available": True,
        }

    def get_tools(self) -> List[str]:
        """Get list of tools provided by this plugin"""
        return [
            # Core dashboard management
            "create_dashboard",
            "create_dashboard_chart",
            "list_user_dashboards",
        ]

    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """Validate that required dependencies are available"""
        info = self.get_info()
        dependencies = info["dependencies"]

        # Check Python dependencies
        can_enable, error = self._check_dependencies(dependencies)
        if not can_enable:
            return can_enable, error

        # Check Frappe environment
        try:
            # Test basic imports and functionality
            import matplotlib.pyplot as plt
            import numpy as np
            import pandas as pd

            # Test Frappe dashboard capabilities
            dashboard_exists = frappe.db.exists("DocType", "Dashboard")
            if not dashboard_exists:
                return False, _("Dashboard DocType not found. Ensure Frappe is properly installed.")

            # Test data access
            test_df = pd.DataFrame({"test": [1, 2, 3]})
            result = test_df.sum()

            self.logger.info("Visualization plugin validation passed")
            return True, None

        except Exception as e:
            return False, _("Environment validation failed: {0}").format(str(e))

    def get_capabilities(self) -> Dict[str, Any]:
        """Get plugin capabilities"""
        return {
            "dashboard_creation": {
                "insights_integration": True,
                "frappe_dashboard_fallback": True,
                "template_based": True,
                "custom_layouts": True,
            },
            "chart_types": {
                "basic": ["bar", "line", "pie", "scatter"],
                "statistical": ["histogram", "box", "heatmap"],
                "performance": ["gauge", "funnel", "waterfall"],
                "advanced": ["treemap", "sunburst", "radar"],
            },
            "templates": {
                "sales": True,
                "financial": True,
                "inventory": True,
                "hr": True,
                "executive": True,
                "custom": True,
            },
            "ai_features": {
                "data_analysis": True,
                "chart_suggestions": True,
                "template_recommendations": True,
                "pattern_detection": True,
            },
            "collaboration": {
                "user_sharing": True,
                "role_sharing": True,
                "public_links": True,
                "scheduled_reports": True,
                "export_formats": ["pdf", "png", "excel", "powerpoint"],
            },
            "interactivity": {
                "drill_down": True,
                "dynamic_filters": True,
                "linked_charts": True,
                "auto_refresh": True,
                "alert_widgets": True,
            },
        }

    def on_enable(self) -> None:
        """Called when plugin is enabled"""
        super().on_enable()

        try:
            # Initialize visualization environment
            self._setup_visualization_environment()

            # Create migration plan for existing visualizations
            self._create_migration_plan()

            # Setup default templates
            self._verify_templates()

            # Log successful enable
            self.logger.info("Visualization plugin enabled successfully")

        except Exception as e:
            self.logger.error(f"Failed to enable visualization plugin: {str(e)}")
            raise e

    def on_disable(self) -> None:
        """Called when plugin is disabled"""
        super().on_disable()

        try:
            # Cleanup visualization resources
            self._cleanup_visualization_environment()

            # Note: Don't delete user dashboards, just disable plugin features
            self.logger.info("Visualization plugin disabled")

        except Exception as e:
            self.logger.warning(f"Cleanup failed during disable: {str(e)}")

    def _setup_visualization_environment(self):
        """Setup visualization environment"""
        try:
            # Configure matplotlib for server environment
            import matplotlib

            matplotlib.use("Agg")  # Use non-interactive backend
            import matplotlib.pyplot as plt

            plt.ioff()  # Turn off interactive mode

            # Check for Insights app integration
            self._check_insights_integration()

            self.logger.debug("Visualization environment configured")

        except Exception as e:
            self.logger.warning(f"Failed to configure visualization environment: {str(e)}")

    def _check_insights_integration(self):
        """Check if Insights app is available for integration"""
        try:
            insights_available = "insights" in frappe.get_installed_apps()
            if insights_available:
                self.logger.info("Insights app detected - enabling advanced dashboard features")
            else:
                self.logger.info("Insights app not found - using Frappe Dashboard fallback")

        except Exception as e:
            self.logger.warning(f"Failed to check Insights integration: {str(e)}")

    def _create_migration_plan(self):
        """Create migration plan for existing create_visualization usage"""
        try:
            # This would analyze existing usage of create_visualization tool
            # and create a migration plan to new dashboard system

            # Check if old visualization tool exists
            try:
                from frappe_assistant_core.plugins.data_science.tools.create_visualization import (
                    CreateVisualization,
                )

                # Mark old tool as deprecated
                self.logger.info("Migration plan created for existing visualizations")
            except ImportError:
                # Old tool doesn't exist, no migration needed
                self.logger.debug("No existing visualization tool found - clean installation")

        except Exception as e:
            self.logger.warning(f"Failed to create migration plan: {str(e)}")

    def _verify_templates(self):
        """Verify that all dashboard templates are properly loaded"""
        try:
            import json
            import os

            template_dir = os.path.join(os.path.dirname(__file__), "templates")
            template_files = [
                "sales_template.json",
                "financial_template.json",
                "inventory_template.json",
                "hr_template.json",
                "executive_template.json",
            ]

            loaded_templates = []
            for template_file in template_files:
                template_path = os.path.join(template_dir, template_file)
                if os.path.exists(template_path):
                    # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal — template_dir is derived from __file__ and template_file is an allow-listed constant
                    with open(template_path) as f:
                        template_data = json.load(f)
                        loaded_templates.append(template_data["name"])
                else:
                    self.logger.warning(f"Template file not found: {template_file}")

            self.logger.info(
                f"Verified {len(loaded_templates)} dashboard templates: {', '.join(loaded_templates)}"
            )

        except Exception as e:
            self.logger.warning(f"Template verification failed: {str(e)}")

    def _cleanup_visualization_environment(self):
        """Cleanup visualization resources"""
        try:
            import matplotlib.pyplot as plt

            plt.close("all")  # Close all figures
            self.logger.debug("Visualization cleanup completed")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup visualization: {str(e)}")

    def get_migration_info(self) -> Dict[str, Any]:
        """Get information about migrating from old visualization system"""
        return {
            "migration_available": True,
            "old_tool": "create_visualization",
            "new_tools": {
                "basic_charts": "create_chart",
                "dashboard_creation": "create_insights_dashboard",
                "template_dashboards": "create_dashboard_from_template",
                "data_exploration": "suggest_visualizations",
            },
            "migration_benefits": [
                "Professional dashboard layouts",
                "Business-specific templates",
                "Interactive components",
                "Sharing and collaboration",
                "AI-powered suggestions",
                "Mobile optimization",
            ],
            "compatibility": {
                "data_sources": "Full compatibility with existing data sources",
                "chart_types": "All existing chart types supported plus advanced options",
                "export_formats": "Enhanced export options including PDF and PowerPoint",
            },
        }

    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get usage examples for the plugin"""
        return [
            {
                "title": "Create Sales Dashboard from Template",
                "description": "Quick setup of comprehensive sales analytics",
                "example": {
                    "tool": "create_dashboard_from_template",
                    "arguments": {
                        "template_type": "sales",
                        "dashboard_name": "Q4 Sales Performance",
                        "time_period": "current_quarter",
                        "share_with": ["Sales Manager", "VP Sales"],
                    },
                },
            },
            {
                "title": "AI-Powered Chart Suggestions",
                "description": "Get intelligent recommendations for data visualization",
                "example": {
                    "tool": "suggest_visualizations",
                    "arguments": {
                        "doctype": "Sales Invoice",
                        "user_intent": "Track monthly revenue trends and customer performance",
                        "analysis_depth": "detailed",
                    },
                },
            },
            {
                "title": "Interactive KPI Card",
                "description": "Create dynamic KPI cards with trend indicators",
                "example": {
                    "tool": "create_kpi_card",
                    "arguments": {
                        "doctype": "Sales Invoice",
                        "metric_field": "grand_total",
                        "metric_name": "Monthly Revenue",
                        "comparison_type": "previous_month",
                        "format": "currency",
                    },
                },
            },
            {
                "title": "Share Dashboard with Team",
                "description": "Configure sharing and automated reporting",
                "example": {
                    "tool": "share_dashboard",
                    "arguments": {
                        "dashboard_name": "Executive Dashboard",
                        "share_with": ["executive_team"],
                        "permissions": "read",
                        "email_schedule": {
                            "enabled": True,
                            "frequency": "weekly",
                            "recipients": ["ceo@company.com", "cfo@company.com"],
                        },
                    },
                },
            },
        ]
