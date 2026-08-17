"""
Enterprise Scanner Plugin - Module Initialization

Exposes all tools and plugin functionality.
"""

from .plugin import EnterpriseScannerPlugin
from .decision_intent_analyzer import DecisionIntentAnalyzerTool
from .enterprise_scanner_engine import EnterpriseScanner
from .data_source_mapper import DataSourceMapper
from .evidence_collector import EvidenceCollector

__version__ = "1.0.0"
__all__ = [
    "EnterpriseScannerPlugin",
    "DecisionIntentAnalyzerTool",
    "EnterpriseScanner",
    "DataSourceMapper",
    "EvidenceCollector",
]


def get_plugin():
    """Get plugin instance."""
    return EnterpriseScannerPlugin()
