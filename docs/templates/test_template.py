"""
Test Template for Example Category Tools (Updated to match actual patterns)
Template for creating comprehensive test suites for new tool categories

Instructions:
1. Replace [ToolCategory] with your tool category name (e.g., "Analytics", "Reporting")
2. Replace example with lowercase version (e.g., "analytics", "reporting")
3. Replace example_tools with actual tool file name (e.g., "analytics_tools")
4. Update test scenarios based on your specific tool functionality
5. Add additional test methods as needed for comprehensive coverage
"""

import frappe
import unittest
import json
from unittest.mock import patch, MagicMock
from frappe_assistant_core.tools.example_tools import ExampleTools
from frappe_assistant_core.tests.base_test import BaseAssistantTest, TestDataBuilder

class TestExampleTools(BaseAssistantTest):
    """Test suite for example tools functionality"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        self.tools = ExampleTools()
    
    def test_get_tools_structure(self):
        """Test that get_tools returns proper structure"""
        tools = ExampleTools.get_tools()
        
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        
        # Check each tool has required fields
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertIsInstance(tool["inputSchema"], dict)
            
            # Validate MCP schema structure
            schema = tool["inputSchema"]
            self.assertIn("type", schema)
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)
            self.assertIsInstance(schema["properties"], dict)
    
    def test_operation_1_basic(self):
        """Test basic operation 1 functionality"""
        # Mock operation result
        mock_operation_result = {
            "processed": True,
            "additional_info": "Operation completed"
        }
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True), \
             patch('frappe.log_error'), \
             patch('example_module.perform_operation_1_logic', return_value=mock_operation_result):
            
            result = ExampleTools.operation_1("Test DocType", "TEST-001", "optional_value")
            
            self.assertTrue(result.get("success"))
            self.assertEqual(result["doctype"], "Test DocType")
            self.assertEqual(result["name"], "TEST-001")
            self.assertIn("data", result)
            self.assertEqual(result["optional_param_used"], "optional_value")
    
    def test_operation_1_no_doctype_exists(self):
        """Test operation 1 with non-existent DocType"""
        with patch('frappe.db.exists', return_value=False):
            result = ExampleTools.operation_1("NonExistent DocType", "TEST-001")
            
            self.assertFalse(result.get("success"))
            self.assertIn("does not exist", result.get("error", ""))
    
    def test_operation_1_no_permission(self):
        """Test operation 1 without permission"""
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=False):
            
            result = ExampleTools.operation_1("Test DocType", "TEST-001")
            
            self.assertFalse(result.get("success"))
            self.assertIn("permission", result.get("error", "").lower())
    
    def test_operation_1_empty_name(self):
        """Test operation 1 with empty name"""
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True):
            
            result = ExampleTools.operation_1("Test DocType", "")
            
            self.assertFalse(result.get("success"))
            self.assertIn("required", result.get("error", "").lower())
    
    def test_operation_1_document_not_exists(self):
        """Test operation 1 with non-existent document"""
        with patch('frappe.db.exists') as mock_exists:
            # DocType exists, but document doesn't
            mock_exists.side_effect = lambda dt, name=None: dt == "Test DocType" and name != "NONEXISTENT-001"
            
            with patch('frappe.has_permission', return_value=True):
                result = ExampleTools.operation_1("Test DocType", "NONEXISTENT-001")
                
                self.assertFalse(result.get("success"))
                self.assertIn("does not exist", result.get("error", ""))
    
    def test_operation_2_basic(self):
        """Test basic operation 2 functionality"""
        # Mock operation results
        mock_results = [
            {
                "name": "DOC-001",
                "processed_data": {"field": "value1"},
                "processing_timestamp": "2024-01-01 10:00:00"
            },
            {
                "name": "DOC-002", 
                "processed_data": {"field": "value2"},
                "processing_timestamp": "2024-01-01 11:00:00"
            }
        ]
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True), \
             patch('frappe.log_error'), \
             patch('example_module.perform_operation_2_logic', return_value=mock_results):
            
            filters = {"status": "Active"}
            result = ExampleTools.operation_2("Test DocType", filters, 10)
            
            self.assertTrue(result.get("success"))
            self.assertEqual(result["doctype"], "Test DocType")
            self.assertEqual(len(result["results"]), 2)
            self.assertEqual(result["total_count"], 2)
            self.assertEqual(result["filters_applied"], filters)
            self.assertEqual(result["limit_used"], 10)
    
    def test_operation_2_default_params(self):
        """Test operation 2 with default parameters"""
        mock_results = [{"name": "DOC-001"}]
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True), \
             patch('frappe.log_error'), \
             patch('example_module.perform_operation_2_logic', return_value=mock_results):
            
            result = ExampleTools.operation_2("Test DocType")
            
            self.assertTrue(result.get("success"))
            self.assertEqual(result["limit_used"], 20)  # Default limit
            self.assertEqual(result["filters_applied"], {})  # Empty filters
    
    def test_operation_2_invalid_limit(self):
        """Test operation 2 with invalid limit values"""
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True):
            
            # Test negative limit
            result = ExampleTools.operation_2("Test DocType", None, -1)
            self.assertFalse(result.get("success"))
            self.assertIn("between 1 and 1000", result.get("error", ""))
            
            # Test limit too large
            result = ExampleTools.operation_2("Test DocType", None, 2000)
            self.assertFalse(result.get("success"))
            self.assertIn("between 1 and 1000", result.get("error", ""))
    
    def test_operation_2_no_doctype_exists(self):
        """Test operation 2 with non-existent DocType"""
        with patch('frappe.db.exists', return_value=False):
            result = ExampleTools.operation_2("NonExistent DocType")
            
            self.assertFalse(result.get("success"))
            self.assertIn("does not exist", result.get("error", ""))
    
    def test_operation_2_no_permission(self):
        """Test operation 2 without permission"""
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=False):
            
            result = ExampleTools.operation_2("Test DocType")
            
            self.assertFalse(result.get("success"))
            self.assertIn("permission", result.get("error", "").lower())
    
    def test_execute_tool_routing(self):
        """Test tool execution routing"""
        valid_tools = [
            "example_operation_1",
            "example_operation_2"
        ]
        
        for tool_name in valid_tools:
            try:
                result = ExampleTools.execute_tool(tool_name, {})
                self.assertIsInstance(result, dict)
            except Exception:
                # Expected for some tools due to missing arguments
                pass
    
    def test_execute_tool_invalid_tool(self):
        """Test execution of invalid tool name"""
        with self.assertRaises(Exception):
            ExampleTools.execute_tool("invalid_tool_name", {})

class TestExampleToolsIntegration(BaseAssistantTest):
    """Integration tests for example tools"""
    
    def setUp(self):
        """Set up integration test environment"""
        super().setUp()
    
    def test_complete_example_workflow(self):
        """Test complete example workflow"""
        # Mock operation data
        mock_operation_1_result = {
            "processed": True,
            "workflow_id": "workflow-123"
        }
        
        mock_operation_2_results = [
            {"name": "RESULT-001", "workflow_id": "workflow-123"},
            {"name": "RESULT-002", "workflow_id": "workflow-123"}
        ]
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True):
            
            # Step 1: Perform operation 1
            with patch('frappe.log_error'), \
                 patch('example_module.perform_operation_1_logic', return_value=mock_operation_1_result):
                result1 = ExampleTools.operation_1("Test DocType", "WORKFLOW-001")
                self.assertTrue(result1.get("success"))
                workflow_id = result1["data"]["workflow_id"]
            
            # Step 2: Use result from step 1 in operation 2
            with patch('frappe.log_error'), \
                 patch('example_module.perform_operation_2_logic', return_value=mock_operation_2_results):
                filters = {"workflow_id": workflow_id}
                result2 = ExampleTools.operation_2("Test DocType", filters)
                self.assertTrue(result2.get("success"))
                self.assertEqual(len(result2["results"]), 2)
            
            # Verify workflow consistency
            self.assertEqual(workflow_id, "workflow-123")
            for result in result2["results"]:
                self.assertEqual(result["workflow_id"], workflow_id)
    
    def test_example_permissions_and_security(self):
        """Test example permissions and security"""
        security_scenarios = [
            {
                "operation": "operation_1",
                "args": {"doctype": "Sensitive DocType", "name": "SENS-001"},
                "requires_permission": True
            },
            {
                "operation": "operation_2",
                "args": {"doctype": "Sensitive DocType"},
                "requires_permission": True
            }
        ]
        
        for scenario in security_scenarios:
            # Test with permission
            with patch('frappe.db.exists', return_value=True), \
                 patch('frappe.has_permission', return_value=True), \
                 patch('frappe.log_error'):
                try:
                    method = getattr(ExampleTools, scenario["operation"])
                    result = method(**scenario["args"])
                    # Should not fail due to permissions (may fail due to missing mocks)
                except Exception:
                    # May fail due to missing mocks, but not permissions
                    pass
            
            # Test without permission
            if scenario["requires_permission"]:
                with patch('frappe.db.exists', return_value=True), \
                     patch('frappe.has_permission', return_value=False), \
                     patch('frappe.log_error'):
                    
                    method = getattr(ExampleTools, scenario["operation"])
                    result = method(**scenario["args"])
                    self.assertFalse(result.get("success"))
                    self.assertIn("permission", result.get("error", "").lower())
    
    def test_example_performance_with_large_dataset(self):
        """Test example performance with large dataset"""
        # Create large mock dataset
        large_dataset = [
            {
                "name": f"DOC-{i:04d}",
                "processed_data": {"field": f"value{i}"},
                "processing_timestamp": f"2024-01-01 {i%24:02d}:00:00"
            }
            for i in range(500)
        ]
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True), \
             patch('frappe.log_error'), \
             patch('example_module.perform_operation_2_logic', return_value=large_dataset):
            
            result, execution_time = self.measure_execution_time(
                ExampleTools.operation_2,
                "Test DocType", {}, 500
            )
            
            self.assertTrue(result.get("success"))
            self.assertEqual(result["total_count"], 500)
            self.assertLess(execution_time, 3.0)  # Should complete within 3 seconds
    
    def test_example_error_scenarios(self):
        """Test various error scenarios in example operations"""
        error_scenarios = [
            {
                "operation": "operation_1",
                "setup": lambda: patch('example_module.perform_operation_1_logic', side_effect=Exception("Operation error")),
                "args": {"doctype": "Test DocType", "name": "ERROR-001"},
                "expected_error": "operation error"
            },
            {
                "operation": "operation_2",
                "setup": lambda: patch('example_module.perform_operation_2_logic', side_effect=Exception("Database error")),
                "args": {"doctype": "Test DocType"},
                "expected_error": "database error"
            }
        ]
        
        for scenario in error_scenarios:
            with scenario["setup"](), \
                 patch('frappe.db.exists', return_value=True), \
                 patch('frappe.has_permission', return_value=True), \
                 patch('frappe.log_error'):
                
                method = getattr(ExampleTools, scenario["operation"])
                result = method(**scenario["args"])
                
                self.assertFalse(result.get("success"))
                self.assertIn(scenario["expected_error"], result.get("error", "").lower())
    
    def test_example_data_consistency(self):
        """Test data consistency across example operations"""
        # Mock consistent data across operations
        base_data = {
            "name": "CONSISTENCY-001",
            "status": "Active",
            "category": "example_test",
            "created_by": "test_user"
        }
        
        mock_operation_1_result = {
            "processed": True,
            "document_data": base_data,
            "processing_id": "proc-123"
        }
        
        mock_operation_2_results = [
            {
                "name": base_data["name"],
                "processed_data": base_data,
                "processing_timestamp": "2024-01-01 10:00:00"
            }
        ]
        
        with patch('frappe.db.exists', return_value=True), \
             patch('frappe.has_permission', return_value=True), \
             patch('frappe.log_error'):
            
            # Operation 1
            with patch('example_module.perform_operation_1_logic', return_value=mock_operation_1_result):
                result1 = ExampleTools.operation_1("Test DocType", base_data["name"])
                self.assertTrue(result1.get("success"))
            
            # Operation 2
            with patch('example_module.perform_operation_2_logic', return_value=mock_operation_2_results):
                result2 = ExampleTools.operation_2("Test DocType", {"name": base_data["name"]})
                self.assertTrue(result2.get("success"))
            
            # Verify data consistency
            self.assertEqual(
                result1["data"]["document_data"]["name"],
                result2["results"][0]["name"]
            )
            self.assertEqual(
                result1["data"]["document_data"]["status"],
                result2["results"][0]["processed_data"]["status"]
            )

if __name__ == "__main__":
    unittest.main()