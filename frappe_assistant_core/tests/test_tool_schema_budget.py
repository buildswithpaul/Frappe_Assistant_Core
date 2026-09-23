import json

from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.tests.base_test import BaseAssistantTest

BUDGETS = {
    "create_dashboard_chart": 2200,
    "run_python_code": 2200,
    "generate_document": 2000,
    "analyze_business_data": 1900,
    "report_requirements": 1600,
    "create_dashboard": 1500,
}


class TestToolSchemaBudget(BaseAssistantTest):
    def test_the_largest_tools_stay_within_budget(self):
        registry = get_tool_registry()
        oversized = []
        for name, budget in BUDGETS.items():
            tool = registry.get_tool(name)
            if tool is None:
                continue
            size = len(
                json.dumps(
                    {
                        "name": name,
                        "description": getattr(tool, "description", ""),
                        "inputSchema": getattr(tool, "inputSchema", {}),
                    },
                    default=str,
                    separators=(",", ":"),
                )
            )
            if size > budget:
                oversized.append(f"{name}: {size} > {budget}")
        self.assertEqual(oversized, [], "\n".join(oversized))
