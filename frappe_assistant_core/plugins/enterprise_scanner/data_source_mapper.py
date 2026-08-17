"""
Data Source Mapper

Maps business data from Frappe docfields to standardized intelligence metrics.
"""

from typing import Dict, List, Any, Optional, Tuple
import frappe
from ..enhanced_base_tool import EnhancedBaseTool
from ..constants import BusinessArea, ScanType
from ..decorators import cache_result, log_performance
from ..exceptions import DataSourceError


class DataSourceMapper(EnhancedBaseTool):
    """
    Data Source Mapper
    
    Maps Frappe docfields to standardized metrics:
    - Customer data mapping
    - Product/Item data mapping
    - Sales Order data mapping
    - Purchase Order data mapping
    - GL Entry financial data mapping
    - Custom field mapping
    """

    name = "data_source_mapper"
    description = "Maps Frappe data to standardized intelligence metrics"

    # Field mappings for each data source
    CUSTOMER_MAPPING = {
        "name": "customer_id",
        "customer_name": "name",
        "territory": "region",
        "customer_group": "segment",
        "credit_limit": "credit_limit",
        "disabled": "is_inactive",
    }

    ITEM_MAPPING = {
        "name": "item_code",
        "item_name": "name",
        "item_group": "category",
        "valuation_rate": "unit_cost",
        "disabled": "is_inactive",
    }

    SALES_ORDER_MAPPING = {
        "name": "order_id",
        "customer": "customer_id",
        "posting_date": "order_date",
        "total": "total_amount",
        "grand_total": "total_with_tax",
        "status": "order_status",
    }

    def _execute_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data source mapping."""
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})
        fields = arguments.get("fields", [])
        
        if not doctype:
            raise DataSourceError("doctype is required")

        try:
            # Get data from Frappe
            data = frappe.get_list(doctype, filters=filters, fields=fields or None)
            
            # Map to standardized format
            mapped_data = self._map_data(doctype, data)
            
            return {
                "success": True,
                "doctype": doctype,
                "record_count": len(mapped_data),
                "data": mapped_data,
                "mapping_applied": True,
                "confidence": 92.0,
            }

        except Exception as e:
            raise DataSourceError(f"Data mapping failed: {str(e)}")

    @cache_result(duration=1800, key_prefix="data_mapping")
    def _map_data(self, doctype: str, data: List[Dict]) -> List[Dict]:
        """Map raw data to standardized format."""
        if not data:
            return []

        # Get appropriate mapping
        mapping = self._get_mapping(doctype)
        
        if not mapping:
            return data

        # Apply mapping
        mapped_data = []
        for record in data:
            mapped_record = {}
            for source_field, target_field in mapping.items():
                if source_field in record:
                    mapped_record[target_field] = record[source_field]
            
            # Keep unmapped fields
            for key, value in record.items():
                if key not in mapping:
                    mapped_record[key] = value
            
            mapped_data.append(mapped_record)

        return mapped_data

    def _get_mapping(self, doctype: str) -> Optional[Dict[str, str]]:
        """Get mapping for doctype."""
        mappings = {
            "Customer": self.CUSTOMER_MAPPING,
            "Item": self.ITEM_MAPPING,
            "Sales Order": self.SALES_ORDER_MAPPING,
        }
        return mappings.get(doctype)

    @log_performance(threshold_ms=2000)
    def get_customer_data(self, company: str) -> List[Dict[str, Any]]:
        """Get and map customer data."""
        try:
            customers = frappe.get_list(
                "Customer",
                filters={"disabled": 0},
                fields=[
                    "name", "customer_name", "territory", "customer_group",
                    "credit_limit", "creation", "modified"
                ],
                limit_page_length=0
            )
            return self._map_data("Customer", customers)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch customer data: {str(e)}")

    @log_performance(threshold_ms=2000)
    def get_product_data(self, company: str) -> List[Dict[str, Any]]:
        """Get and map product/item data."""
        try:
            items = frappe.get_list(
                "Item",
                filters={"disabled": 0, "is_sales_item": 1},
                fields=[
                    "name", "item_name", "item_group", "valuation_rate",
                    "creation", "modified"
                ],
                limit_page_length=0
            )
            return self._map_data("Item", items)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch product data: {str(e)}")

    @log_performance(threshold_ms=2500)
    def get_sales_data(self, company: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """Get and map sales order data."""
        try:
            sales_orders = frappe.get_list(
                "Sales Order",
                filters={
                    "company": company,
                    "docstatus": 1,
                    "posting_date": ["between", [date_from, date_to]]
                },
                fields=[
                    "name", "customer", "posting_date", "total",
                    "grand_total", "status", "creation"
                ],
                limit_page_length=0
            )
            return self._map_data("Sales Order", sales_orders)
        except Exception as e:
            raise DataSourceError(f"Failed to fetch sales data: {str(e)}")

    @log_performance(threshold_ms=2500)
    def get_purchase_data(self, company: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """Get and map purchase order data."""
        try:
            purchase_orders = frappe.get_list(
                "Purchase Order",
                filters={
                    "company": company,
                    "docstatus": 1,
                    "posting_date": ["between", [date_from, date_to]]
                },
                fields=[
                    "name", "supplier", "posting_date", "total",
                    "grand_total", "status"
                ],
                limit_page_length=0
            )
            return purchase_orders
        except Exception as e:
            raise DataSourceError(f"Failed to fetch purchase data: {str(e)}")

    @log_performance(threshold_ms=3000)
    def get_financial_data(self, company: str, account_head: str = None) -> List[Dict[str, Any]]:
        """Get financial GL entries."""
        try:
            filters = {"company": company}
            if account_head:
                filters["account"] = account_head

            gl_entries = frappe.get_list(
                "GL Entry",
                filters=filters,
                fields=[
                    "name", "account", "posting_date", "debit", "credit",
                    "reference_type", "reference_name"
                ],
                limit_page_length=0
            )
            return gl_entries
        except Exception as e:
            raise DataSourceError(f"Failed to fetch financial data: {str(e)}")

    def get_data_lineage(self, doctype: str, document_name: str) -> Dict[str, Any]:
        """Get data lineage/relationships for a document."""
        try:
            doc = frappe.get_doc(doctype, document_name)
            
            lineage = {
                "doctype": doctype,
                "document": document_name,
                "created": doc.creation,
                "modified": doc.modified,
                "created_by": doc.owner,
                "links": self._extract_links(doc),
            }
            
            return lineage
        except Exception as e:
            raise DataSourceError(f"Failed to get data lineage: {str(e)}")

    def _extract_links(self, doc: Any) -> List[Dict[str, str]]:
        """Extract link relationships from document."""
        links = []
        
        # Get all fields
        for field in doc.meta.fields:
            if field.fieldtype == "Link":
                value = doc.get(field.fieldname)
                if value:
                    links.append({
                        "field": field.fieldname,
                        "doctype": field.options,
                        "value": value
                    })
        
        return links

    def validate_data_quality(self, doctype: str, record: Dict) -> Tuple[bool, List[str]]:
        """Validate data quality of a record."""
        issues = []
        
        # Check for required fields
        required_fields = self._get_required_fields(doctype)
        for field in required_fields:
            if field not in record or not record[field]:
                issues.append(f"Required field '{field}' is missing or empty")
        
        # Check data types
        type_issues = self._validate_data_types(doctype, record)
        issues.extend(type_issues)
        
        return len(issues) == 0, issues

    def _get_required_fields(self, doctype: str) -> List[str]:
        """Get required fields for doctype."""
        required = {
            "Customer": ["customer_name", "customer_group"],
            "Item": ["item_name", "item_group"],
            "Sales Order": ["customer", "posting_date", "total"],
        }
        return required.get(doctype, [])

    def _validate_data_types(self, doctype: str, record: Dict) -> List[str]:
        """Validate data types in record."""
        issues = []
        
        type_rules = {
            "Sales Order": {
                "total": (float, int),
                "posting_date": str,
            },
            "Customer": {
                "credit_limit": (float, int),
            },
        }
        
        rules = type_rules.get(doctype, {})
        for field, expected_type in rules.items():
            if field in record and record[field] is not None:
                if not isinstance(record[field], expected_type):
                    issues.append(
                        f"Field '{field}' has invalid type: "
                        f"expected {expected_type}, got {type(record[field])}"
                    )
        
        return issues
