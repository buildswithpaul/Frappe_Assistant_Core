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

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

class AssistantAuditLog(Document):
    """assistant Audit Log DocType controller"""
    
    def before_insert(self):
        """Set default values before inserting"""
        if not self.timestamp:
            self.timestamp = now()
        
        # Set IP address if available
        if hasattr(frappe.local, 'request_ip') and not self.ip_address:
            self.ip_address = frappe.local.request_ip
    
    def validate(self):
        """Validate audit log entry"""
        # Ensure required fields are set
        if not self.user:
            self.user = frappe.session.user
        
        if not self.timestamp:
            self.timestamp = now()
    
    def get_formatted_execution_time(self):
        """Get formatted execution time"""
        if self.execution_time:
            if self.execution_time < 1:
                return f"{self.execution_time * 1000:.0f}ms"
            else:
                return f"{self.execution_time:.2f}s"
        return "N/A"

@frappe.whitelist()
def get_audit_statistics():
    """Get audit statistics for dashboard"""
    today = frappe.utils.today()
    
    # Total actions today
    total_today = frappe.db.count("assistant Audit Log", 
                                  filters={"creation": [">=", today]})
    
    # Success rate today
    successful_today = frappe.db.count("assistant Audit Log", 
                                       filters={"creation": [">=", today], "status": "Success"})
    
    success_rate = (successful_today / total_today * 100) if total_today > 0 else 0
    
    # Most used tools today
    most_used_tools = frappe.db.sql("""
        SELECT tool_name, COUNT(*) as count
        FROM `tabassistant Audit Log`
        WHERE DATE(creation) = %s AND tool_name IS NOT NULL
        GROUP BY tool_name
        ORDER BY count DESC
        LIMIT 5
    """, (today,), as_dict=True)
    
    # Average execution time
    avg_execution_time = frappe.db.sql("""
        SELECT AVG(execution_time) as avg_time
        FROM `tabassistant Audit Log`
        WHERE DATE(creation) = %s AND execution_time IS NOT NULL
    """, (today,))[0][0] or 0
    
    return {
        "total_actions_today": total_today,
        "success_rate": round(success_rate, 2),
        "most_used_tools": most_used_tools,
        "average_execution_time": round(avg_execution_time, 3) if avg_execution_time else 0
    }

def get_context(context):
    context.title = _("assistant Audit Log")
    context.docs = get_audit_logs()

def get_audit_logs():
    return frappe.get_all("assistant Audit Log", fields=["*"], order_by="creation desc")