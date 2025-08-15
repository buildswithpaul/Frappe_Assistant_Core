# -*- coding: utf-8 -*-
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
Data Science Plugin for Frappe Assistant Core.
Provides Python code execution, data analysis, and visualization tools.
"""

import frappe
from frappe import _
from frappe_assistant_core.plugins.base_plugin import BasePlugin
from typing import Dict, Any, List, Tuple, Optional


class DataSciencePlugin(BasePlugin):
    """
    Plugin for data science and analysis capabilities.
    
    Provides tools for:
    - Python code execution with Frappe context
    - Statistical data analysis with pandas/numpy
    - Business intelligence and insights
    - File processing and AI analysis (PDF, images, CSV, documents)
    """
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            'name': 'data_science',
            'display_name': 'Data Science & Analytics',
            'description': 'Python code execution, statistical analysis, and file processing with AI capabilities',
            'version': '1.0.0',
            'author': 'Frappe Assistant Core Team',
            'dependencies': [
                'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 'scipy'
            ],
            'requires_restart': False
        }
    
    def get_tools(self) -> List[str]:
        """Get list of tools provided by this plugin"""
        return [
            'run_python_code',
            'analyze_business_data',
            'run_database_query',
            'extract_file_content'  # File content extraction tool
        ]
    
    def validate_environment(self) -> Tuple[bool, Optional[str]]:
        """Validate that required dependencies are available"""
        info = self.get_info()
        dependencies = info['dependencies']
        
        # Check Python dependencies
        can_enable, error = self._check_dependencies(dependencies)
        if not can_enable:
            return can_enable, error
        
        # Check if Python code execution is allowed
        try:
            # Test basic imports
            import pandas as pd
            import numpy as np
            import matplotlib.pyplot as plt
            
            # Basic functionality test
            df = pd.DataFrame({'test': [1, 2, 3]})
            result = df.sum()
            
            self.logger.info("Data science plugin validation passed")
            return True, None
            
        except Exception as e:
            return False, _("Environment validation failed: {0}").format(str(e))
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get plugin capabilities"""
        return {
            "experimental": {
                "data_analysis": True,
                "python_execution": True,
                "statistical_analysis": True,
                "business_intelligence": True
            },
            "data_formats": {
                "pandas": True,
                "numpy": True,
                "json": True,
                "csv": True
            },
            "analysis_types": {
                "statistical": True,
                "correlation": True,
                "aggregation": True,
                "custom_calculations": True
            }
        }
    
    def on_enable(self) -> None:
        """Called when plugin is enabled"""
        super().on_enable()
        
        # Initialize any required settings
        self._setup_matplotlib_backend()
        
        # Log successful enable
        self.logger.info("Data science plugin enabled with visualization support")
    
    def on_disable(self) -> None:
        """Called when plugin is disabled"""
        super().on_disable()
        
        # Cleanup any resources
        self._cleanup_matplotlib()
    
    def _setup_matplotlib_backend(self):
        """Setup matplotlib backend for server environment"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            plt.ioff()  # Turn off interactive mode
            
            self.logger.debug("Matplotlib backend configured for server environment")
        except Exception as e:
            self.logger.warning(f"Failed to configure matplotlib: {str(e)}")
    
    def _cleanup_matplotlib(self):
        """Cleanup matplotlib resources"""
        try:
            import matplotlib.pyplot as plt
            plt.close('all')  # Close all figures
            self.logger.debug("Matplotlib cleanup completed")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup matplotlib: {str(e)}")
    
